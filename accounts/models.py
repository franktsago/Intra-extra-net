"""Comptes utilisateurs, rôles et journal d'activité.

Le système distingue deux périmètres d'accès :
  • INTRANET  — employés de LPM Consulting Group (admin, RH, responsables, employés)
  • EXTRANET  — utilisateurs externes (clients, partenaires, fournisseurs, consultants)

La séparation intranet/extranet est portée par le rôle de l'utilisateur, ce qui
permet un cloisonnement strict des accès comme exigé par le cahier des charges.
"""

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class Role(models.TextChoices):
    # --- Intranet ---
    ADMIN = "ADMIN", "Administrateur principal"
    CEO = "CEO", "Directeur Général (CEO)"
    RH = "RH", "Responsable RH"
    MANAGER = "MANAGER", "Responsable de service"
    EMPLOYE = "EMPLOYE", "Employé"
    STAGIAIRE = "STAGIAIRE", "Stagiaire"
    # --- Extranet ---
    CLIENT = "CLIENT", "Client"
    PARTENAIRE = "PARTENAIRE", "Partenaire"
    FOURNISSEUR = "FOURNISSEUR", "Fournisseur"
    CONSULTANT = "CONSULTANT", "Consultant externe"


# Le stagiaire partage exactement l'interface et les droits de l'employé.
INTRANET_ROLES = {Role.ADMIN, Role.CEO, Role.RH, Role.MANAGER, Role.EMPLOYE, Role.STAGIAIRE}
EXTRANET_ROLES = {Role.CLIENT, Role.PARTENAIRE, Role.FOURNISSEUR, Role.CONSULTANT}


class User(AbstractUser):
    """Compte d'accès unique pour l'intranet et l'extranet."""

    role = models.CharField(
        "Rôle principal", max_length=20, choices=Role.choices, default=Role.EMPLOYE
    )
    secondary_roles = models.CharField(
        "Rôles supplémentaires", max_length=120, blank=True,
        help_text="Codes de rôles séparés par des virgules (ex. RH,MANAGER). "
                  "Permet à l'utilisateur de basculer entre plusieurs fonctions.",
    )
    phone = models.CharField("Téléphone", max_length=30, blank=True)
    avatar = models.ImageField("Photo", upload_to="avatars/", blank=True, null=True)
    last_seen = models.DateTimeField("Dernière activité", null=True, blank=True, editable=False)
    # Signature manuscrite et cachet (PNG transparent conseillé) — utilisés pour
    # signer/tamponner les documents officiels (notes de congé, attestations…).
    # Réservés aux signataires habilités (RH, CEO, admin).
    signature = models.ImageField("Signature", upload_to="signatures/", blank=True, null=True)
    stamp = models.ImageField("Cachet", upload_to="cachets/", blank=True, null=True)
    must_change_password = models.BooleanField(
        "Doit changer son mot de passe", default=False,
        help_text="Forcé après une création de compte par un administrateur.",
    )
    organization = models.CharField(
        "Organisation externe", max_length=150, blank=True,
        help_text="Société du client/partenaire/fournisseur (extranet).",
    )
    created_by = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="comptes_crees", verbose_name="Créé par",
    )
    linked_accounts = models.ManyToManyField(
        "self", blank=True, verbose_name="Comptes liés",
        help_text="Autres comptes appartenant à la MÊME personne. Permet de "
                  "basculer de l'un à l'autre sans se reconnecter (réservé au "
                  "super administrateur). Chaque action reste tracée.",
    )

    class Meta:
        verbose_name = "Utilisateur"
        verbose_name_plural = "Utilisateurs"
        ordering = ["last_name", "first_name"]

    def __str__(self):
        full = self.get_full_name()
        return f"{full} ({self.get_role_display()})" if full else self.username

    # ----- Rôles multiples / rôle actif ----- #
    @property
    def available_roles(self):
        """Liste ordonnée des rôles que l'utilisateur peut endosser."""
        roles = [self.role]
        for r in self.secondary_roles.split(","):
            r = r.strip()
            if r and r in Role.values and r not in roles:
                roles.append(r)
        return roles

    @property
    def has_multiple_roles(self):
        return len(self.available_roles) > 1

    @property
    def available_roles_display(self):
        """Liste de (code, libellé) pour le sélecteur de rôle."""
        labels = dict(Role.choices)
        return [(r, labels.get(r, r)) for r in self.available_roles]

    @property
    def effective_role(self):
        """Rôle actif courant (peut être basculé en session). Par défaut : rôle principal."""
        active = getattr(self, "_active_role", None)
        if active and active in self.available_roles:
            return active
        return self.role

    @property
    def effective_role_display(self):
        return dict(Role.choices).get(self.effective_role, self.effective_role)

    # ----- Helpers de périmètre / permissions (basés sur le rôle ACTIF) ----- #
    @property
    def is_external(self) -> bool:
        return self.effective_role in EXTRANET_ROLES

    @property
    def is_internal(self) -> bool:
        return self.effective_role in INTRANET_ROLES

    @property
    def is_admin_lpm(self) -> bool:
        """Super administrateur (accès total). Le CEO n'en fait pas partie.

        Si l'utilisateur a explicitement choisi un rôle actif (multi-rôles),
        on respecte STRICTEMENT ce rôle pour que l'interface s'adapte. Sinon,
        un superuser conserve les pleins droits par défaut.
        """
        if getattr(self, "_active_role", None):
            return self.effective_role == Role.ADMIN
        return self.role == Role.ADMIN or self.is_superuser

    @property
    def is_ceo(self) -> bool:
        """Directeur Général — super-admin secondaire (sous l'admin principal)."""
        return self.effective_role == Role.CEO or self.is_admin_lpm

    @property
    def is_rh(self) -> bool:
        return self.effective_role == Role.RH or self.is_ceo

    @property
    def is_manager(self) -> bool:
        return self.effective_role == Role.MANAGER or self.is_rh

    @property
    def can_validate_leave(self) -> bool:
        """Responsables, RH, CEO et admin peuvent valider les congés."""
        return self.effective_role in {Role.MANAGER, Role.RH, Role.CEO, Role.ADMIN} or self.is_admin_lpm

    @property
    def must_clock(self) -> bool:
        """Doit pointer : employé, stagiaire, responsable et RH (pas le CEO/admin)."""
        return self.effective_role in {Role.EMPLOYE, Role.STAGIAIRE, Role.MANAGER, Role.RH}

    @property
    def can_sign(self) -> bool:
        """Signataire habilité (signature + cachet) : responsables, RH, CEO et admin."""
        return self.effective_role in {Role.MANAGER, Role.RH, Role.CEO, Role.ADMIN} or self.is_admin_lpm

    @property
    def is_online(self) -> bool:
        """En ligne si une activité a eu lieu très récemment (≈ 40 s).

        Les pages « pinguent » le serveur toutes les ~4 s (poll messagerie + appels),
        donc un utilisateur connecté reste en ligne et passe hors ligne ~40 s après
        avoir fermé l'application."""
        if not self.last_seen:
            return False
        from django.utils import timezone
        return (timezone.now() - self.last_seen).total_seconds() < 40

    @property
    def display_initials(self) -> str:
        a = (self.first_name[:1] or self.username[:1]).upper()
        b = (self.last_name[:1]).upper()
        return (a + b) or "?"

    # ----- Comptes liés (même personne) / bascule ----- #
    def linked_group(self):
        """Tous les comptes liés à celui-ci (fermeture transitive, hors soi-même).

        Si A est lié à B et A à C, alors B « voit » aussi C : les trois comptes
        forment un groupe et peuvent basculer entre eux.
        """
        seen = {self.pk}
        frontier = [self]
        while frontier:
            nxt = []
            for u in frontier:
                for peer in u.linked_accounts.all():
                    if peer.pk not in seen:
                        seen.add(peer.pk)
                        nxt.append(peer)
            frontier = nxt
        seen.discard(self.pk)
        return User.objects.filter(pk__in=seen).order_by("last_name", "first_name")

    @property
    def has_linked_accounts(self) -> bool:
        return self.linked_accounts.exists()


class ActivityLog(models.Model):
    """Journal des actions et connexions (exigence de traçabilité du CDC)."""

    class Action(models.TextChoices):
        LOGIN = "LOGIN", "Connexion"
        LOGOUT = "LOGOUT", "Déconnexion"
        LOGIN_FAILED = "LOGIN_FAILED", "Échec de connexion"
        CREATE = "CREATE", "Création"
        UPDATE = "UPDATE", "Modification"
        DELETE = "DELETE", "Suppression"
        DOWNLOAD = "DOWNLOAD", "Téléchargement"
        VIEW = "VIEW", "Consultation"

    user = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="activites", verbose_name="Utilisateur",
    )
    action = models.CharField(max_length=20, choices=Action.choices)
    description = models.CharField(max_length=255, blank=True)
    ip_address = models.GenericIPAddressField("Adresse IP", null=True, blank=True)
    path = models.CharField("Chemin", max_length=255, blank=True)
    created_at = models.DateTimeField("Horodatage", default=timezone.now)

    class Meta:
        verbose_name = "Activité"
        verbose_name_plural = "Journal d'activité"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["-created_at"]), models.Index(fields=["user", "action"])]

    def __str__(self):
        who = self.user.get_username() if self.user else "anonyme"
        return f"{self.get_action_display()} — {who} — {self.created_at:%d/%m/%Y %H:%M}"
