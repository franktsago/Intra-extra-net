"""Gestion documentaire : catégories, documents, contrôle d'accès, archivage."""

import os

from django.conf import settings
from django.db import models
from django.utils import timezone

from accounts.models import Role


class DocumentCategory(models.Model):
    name = models.CharField("Catégorie", max_length=100, unique=True)
    description = models.CharField("Description", max_length=255, blank=True)

    class Meta:
        verbose_name = "Catégorie de document"
        verbose_name_plural = "Catégories de documents"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Document(models.Model):
    class Visibility(models.TextChoices):
        ALL = "ALL", "Tout le personnel"
        # Partages d'un employé (relatifs au déposant) :
        COLLEAGUES = "COLLEAGUES", "Mes collègues (mon département)"
        MY_MANAGER = "MY_MANAGER", "Mon responsable"
        COLLEAGUES_MANAGER = "COLL_MGR", "Mes collègues et mon responsable"
        TEAM = "TEAM", "Mon équipe (responsable)"
        MANAGERS = "MANAGERS", "Responsables et RH"
        RH = "RH", "RH et direction"
        ADMIN = "ADMIN", "Administration uniquement"

    title = models.CharField("Titre", max_length=200)
    category = models.ForeignKey(
        DocumentCategory, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="documents", verbose_name="Catégorie",
    )
    file = models.FileField("Fichier", upload_to="documents/%Y/%m/")
    description = models.TextField("Description", blank=True)
    visibility = models.CharField(
        "Visibilité", max_length=10, choices=Visibility.choices, default=Visibility.ALL
    )
    is_archived = models.BooleanField("Archivé", default=False)
    is_confidential = models.BooleanField(
        "Confidentiel", default=False,
        help_text="Lecture en ligne seule (pas de téléchargement ni d'impression), avec filigrane.",
    )
    team_owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="documents_equipe",
        verbose_name="Responsable de l'équipe",
        help_text="Pour une visibilité « Mon équipe » : le responsable propriétaire.",
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
        related_name="documents_ajoutes", verbose_name="Déposé par",
    )
    download_count = models.PositiveIntegerField("Téléchargements", default=0)
    created_at = models.DateTimeField("Déposé le", default=timezone.now)

    class Meta:
        verbose_name = "Document"
        verbose_name_plural = "Documents"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    @property
    def filename(self):
        return os.path.basename(self.file.name)

    @property
    def extension(self):
        return os.path.splitext(self.file.name)[1].lower().lstrip(".")

    @property
    def is_pdf(self):
        return self.extension == "pdf"

    @property
    def is_image(self):
        return self.extension in {"jpg", "jpeg", "png", "gif", "webp", "bmp", "svg"}

    @property
    def is_word(self):
        return self.extension in {"doc", "docx"}

    @property
    def is_excel(self):
        return self.extension in {"xls", "xlsx", "csv"}

    @property
    def is_powerpoint(self):
        return self.extension in {"ppt", "pptx"}

    @property
    def is_office(self):
        return self.is_word or self.is_excel or self.is_powerpoint

    @property
    def viewer_kind(self):
        """Type de visionneuse à utiliser côté client."""
        if self.is_pdf:
            return "pdf"
        if self.is_image:
            return "image"
        if self.is_word:
            return "word"
        if self.is_excel:
            return "excel"
        if self.is_powerpoint:
            return "pptx"
        return "none"

    @property
    def is_previewable(self):
        """Affichable en ligne (PDF, image, Word, Excel, PowerPoint)."""
        return self.is_pdf or self.is_image or self.is_office

    def _shared_with_colleagues(self, user):
        """Visible par les collègues de département du déposant (+ déposant, RH/direction)."""
        if user.is_rh or self.uploaded_by_id == user.id:
            return True
        if not self.uploaded_by_id:
            return False
        from employees.models import department_colleagues_ids
        return user.id in department_colleagues_ids(self.uploaded_by)

    def _shared_with_manager(self, user):
        """Visible par le responsable hiérarchique du déposant (+ déposant, RH/direction)."""
        if user.is_rh or self.uploaded_by_id == user.id:
            return True
        if not self.uploaded_by_id:
            return False
        from employees.models import Employee
        emp = (Employee.objects.filter(user_id=self.uploaded_by_id)
               .select_related("manager__user").first())
        return bool(emp and emp.manager and emp.manager.user_id == user.id)

    def can_view(self, user):
        if user.is_admin_lpm:
            return True
        if self.visibility == self.Visibility.ALL:
            return user.is_internal
        if self.visibility == self.Visibility.COLLEAGUES:
            return self._shared_with_colleagues(user)
        if self.visibility == self.Visibility.MY_MANAGER:
            return self._shared_with_manager(user)
        if self.visibility == self.Visibility.COLLEAGUES_MANAGER:
            return self._shared_with_colleagues(user) or self._shared_with_manager(user)
        if self.visibility == self.Visibility.TEAM:
            # Le responsable propriétaire, son équipe, et la direction RH/CEO.
            if user.is_rh or self.team_owner_id == user.id:
                return True
            from employees.models import Employee
            return Employee.objects.filter(user=user, manager__user_id=self.team_owner_id).exists()
        if self.visibility == self.Visibility.MANAGERS:
            return user.role in {Role.MANAGER, Role.RH, Role.ADMIN} or user.is_ceo
        if self.visibility == self.Visibility.RH:
            return user.role in {Role.RH, Role.ADMIN} or user.is_ceo
        return False
