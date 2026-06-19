"""Gestion des tâches : création, attribution, suivi, statut, échéances."""

from django.conf import settings
from django.db import models
from django.utils import timezone


class Task(models.Model):
    class Status(models.TextChoices):
        TODO = "TODO", "À faire"
        IN_PROGRESS = "IN_PROGRESS", "En cours"
        DONE = "DONE", "Terminée"
        CANCELLED = "CANCELLED", "Annulée"

    class Priority(models.TextChoices):
        LOW = "LOW", "Basse"
        NORMAL = "NORMAL", "Normale"
        HIGH = "HIGH", "Haute"
        URGENT = "URGENT", "Urgente"

    title = models.CharField("Titre", max_length=200)
    description = models.TextField("Description", blank=True)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="taches_assignees", verbose_name="Assignée à",
    )
    # Tâche partagée : une même tâche peut être assignée à plusieurs membres. Le
    # statut est COMMUN — si l'un la passe à « Terminée », elle l'est pour tous.
    # `assigned_to` reste l'assigné principal (1er membre) pour l'affichage/compat.
    assignees = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True, related_name="taches_partagees",
        verbose_name="Assignée à (équipe)",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
        related_name="taches_creees", verbose_name="Créée par",
    )
    project = models.ForeignKey(
        "projects.Project", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="tasks", verbose_name="Projet",
    )
    status = models.CharField("Statut", max_length=12, choices=Status.choices, default=Status.TODO)
    priority = models.CharField("Priorité", max_length=8, choices=Priority.choices, default=Priority.NORMAL)
    due_date = models.DateField("Échéance", null=True, blank=True)
    # Validation : une tâche créée par un employé doit être approuvée par son responsable.
    is_approved = models.BooleanField("Validée", default=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="taches_validees", verbose_name="Validée par",
    )
    created_at = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Tâche"
        verbose_name_plural = "Tâches"
        ordering = ["status", "due_date", "-priority"]

    def __str__(self):
        return self.title

    @property
    def is_overdue(self):
        return (
            self.due_date and self.status not in {self.Status.DONE, self.Status.CANCELLED}
            and self.due_date < timezone.localdate()
        )

    @property
    def priority_color(self):
        return {"LOW": "slate", "NORMAL": "sky", "HIGH": "amber", "URGENT": "red"}[self.priority]

    @property
    def assignee_ids(self):
        """Ids de tous les assignés (équipe partagée + assigné principal)."""
        ids = set(self.assignees.values_list("id", flat=True))
        if self.assigned_to_id:
            ids.add(self.assigned_to_id)
        return ids


class TaskAttachment(models.Model):
    """Fichier de rendu rattaché à une tâche (livrable envoyé au responsable/équipe).

    Plusieurs fichiers possibles par tâche ; on sait ainsi à quelle tâche
    correspond chaque livrable."""

    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="attachments")
    file = models.FileField("Fichier de rendu", upload_to="tasks/rendus/%Y/%m/")
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
        related_name="task_attachments", verbose_name="Déposé par",
    )
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Rendu de tâche"
        verbose_name_plural = "Rendus de tâche"
        ordering = ["-created_at"]

    def __str__(self):
        import os
        return os.path.basename(self.file.name)

    @property
    def filename(self):
        import os
        return os.path.basename(self.file.name)

    @property
    def ext(self):
        import os
        return os.path.splitext(self.file.name)[1].lower().lstrip(".")
