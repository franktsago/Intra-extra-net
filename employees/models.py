"""Employés, départements, postes et organigramme."""

from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone

# Numéro de téléphone valide : optionnel « + », 8 à 15 chiffres (espaces/points/tirets tolérés).
PHONE_VALIDATOR = RegexValidator(
    r"^\+?\d[\d\s.\-]{7,18}$",
    "Numéro de téléphone invalide (8 à 15 chiffres, ex. +237 6 99 00 00 00).",
)


class Department(models.Model):
    name = models.CharField("Nom du département", max_length=120, unique=True)
    code = models.CharField("Code", max_length=10, blank=True)
    description = models.TextField("Description", blank=True)
    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="departements_diriges", verbose_name="Responsable",
    )
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="sous_departements", verbose_name="Rattaché à",
    )

    class Meta:
        verbose_name = "Département"
        verbose_name_plural = "Départements"
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def headcount(self):
        # Effectif = personnel présent dans l'organisation (au travail OU en congé).
        return self.employees.filter(status__in=WORKFORCE_STATUSES).count()


def _next_birthday(birth_date, today):
    """Prochaine occurrence de l'anniversaire à partir de `today` (gère le 29/02)."""
    def _safe(year):
        try:
            return birth_date.replace(year=year)
        except ValueError:  # 29 février → 28 sur année non bissextile
            return birth_date.replace(year=year, day=28)
    nxt = _safe(today.year)
    if nxt < today:
        nxt = _safe(today.year + 1)
    return nxt


def upcoming_birthdays(employees, within_days=30, today=None):
    """Liste triée des anniversaires à venir : {employee, date, days, age}."""
    today = today or timezone.localdate()
    out = []
    for emp in employees:
        if not emp.birth_date:
            continue
        nxt = _next_birthday(emp.birth_date, today)
        days = (nxt - today).days
        if 0 <= days <= within_days:
            # On ne conserve que jour + mois (année sentinelle) → pas d'âge affiché.
            age = None if emp.birth_date.year >= 2000 else nxt.year - emp.birth_date.year
            out.append({"employee": emp, "date": nxt, "days": days, "age": age})
    out.sort(key=lambda x: x["days"])
    return out


class Position(models.Model):
    title = models.CharField("Intitulé du poste", max_length=150)
    department = models.ForeignKey(
        Department, null=True, blank=True, on_delete=models.CASCADE, related_name="positions",
        verbose_name="Département",
    )

    class Meta:
        verbose_name = "Poste"
        verbose_name_plural = "Postes"
        ordering = ["title"]
        unique_together = ("title", "department")

    def __str__(self):
        return f"{self.title} — {self.department.name}" if self.department else self.title


class Employee(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "En activité"
        LEAVE = "LEAVE", "En congé"
        SUSPENDED = "SUSPENDED", "Suspendu"
        TERMINATED = "TERMINATED", "Sorti des effectifs"

    # Statuts comptés dans l'effectif : présent dans l'organisation, qu'il soit au
    # travail ou en congé. Un congé ne fait pas disparaître l'employé des effectifs
    # ni du pointage (il y figure « En congé »), il le sort seulement des présents.

    class Contract(models.TextChoices):
        CDI = "CDI", "CDI — Contrat à durée indéterminée"
        CDD = "CDD", "CDD — Contrat à durée déterminée"
        STAGE = "STAGE", "Stage"
        TEMP = "TEMP", "Temporaire / Mission"

    class Gender(models.TextChoices):
        M = "M", "Masculin"
        F = "F", "Féminin"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="employee", verbose_name="Compte utilisateur",
    )
    # Attribué automatiquement à la création, en séquence croissante, non modifiable.
    matricule = models.CharField("Matricule", max_length=20, unique=True,
                                 blank=True, editable=False)
    gender = models.CharField("Sexe", max_length=1, choices=Gender.choices, blank=True)
    birth_date = models.DateField("Date de naissance", null=True, blank=True)
    departments = models.ManyToManyField(
        Department, blank=True, related_name="employees", verbose_name="Départements",
    )
    positions = models.ManyToManyField(
        Position, blank=True, related_name="holders", verbose_name="Postes / fonctions",
    )
    manager = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="subordonnes", verbose_name="Responsable hiérarchique",
    )
    hire_date = models.DateField("Date d'embauche", default=timezone.now)
    contract_type = models.CharField(
        "Type de contrat", max_length=10, choices=Contract.choices, default=Contract.CDI
    )
    status = models.CharField(
        "Statut", max_length=12, choices=Status.choices, default=Status.ACTIVE
    )
    cnps_number = models.CharField("N° CNPS", max_length=30, blank=True,
                                   help_text="Caisse Nationale de Prévoyance Sociale")
    address = models.CharField("Adresse", max_length=255, blank=True)
    city = models.CharField("Ville", max_length=80, blank=True, default="Douala")
    # Personne(s) à contacter en cas d'urgence : 1re ligne obligatoire (à la création),
    # 2e ligne optionnelle. Le téléphone est validé.
    emergency_contact = models.CharField("Personne à contacter — Nom", max_length=150, blank=True)
    emergency_contact_phone = models.CharField(
        "Personne à contacter — Téléphone", max_length=30, blank=True,
        validators=[PHONE_VALIDATOR])
    emergency_contact2 = models.CharField("2e contact — Nom (optionnel)", max_length=150, blank=True)
    emergency_contact2_phone = models.CharField(
        "2e contact — Téléphone (optionnel)", max_length=30, blank=True,
        validators=[PHONE_VALIDATOR])

    class Meta:
        verbose_name = "Employé"
        verbose_name_plural = "Employés"
        ordering = ["user__last_name", "user__first_name"]

    def save(self, *args, **kwargs):
        # Matricule auto-attribué (séquence croissante) s'il n'est pas encore défini.
        if not self.matricule:
            self.matricule = generate_matricule()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.full_name} ({self.matricule})"

    @property
    def full_name(self):
        return self.user.get_full_name() or self.user.username

    @property
    def is_intern(self):
        """Stagiaire : d'après le dernier contrat de travail, sinon la fiche, sinon le rôle."""
        latest = self.contracts.order_by("-is_active", "-start_date").first()
        if latest:
            return latest.type == "STAGE"
        if self.contract_type == "STAGE":
            return True
        return getattr(self.user, "role", None) == "STAGIAIRE"

    # --- Compatibilité : « principal » (1er) + libellés multiples ---
    @property
    def department(self):
        """Département principal (le 1er) — pour les documents/affichages mono-valeur."""
        return self.departments.first()

    @property
    def position(self):
        """Poste principal (le 1er)."""
        return self.positions.first()

    @property
    def department_names(self):
        return ", ".join(d.name for d in self.departments.all())

    @property
    def position_titles(self):
        return ", ".join(p.title for p in self.positions.all())

    @property
    def email(self):
        return self.user.email

    @property
    def phone(self):
        return self.user.phone

    @property
    def seniority_years(self):
        """Ancienneté en années révolues (base des droits à congés au Cameroun)."""
        today = timezone.localdate()
        years = today.year - self.hire_date.year
        if (today.month, today.day) < (self.hire_date.month, self.hire_date.day):
            years -= 1
        return max(years, 0)

    @property
    def seniority_months(self):
        today = timezone.localdate()
        return (today.year - self.hire_date.year) * 12 + (today.month - self.hire_date.month)


# Statuts « dans l'effectif » : au travail ou en congé (pas suspendu/sorti).
WORKFORCE_STATUSES = (Employee.Status.ACTIVE, Employee.Status.LEAVE)


def generate_matricule():
    """Prochain matricule en séquence croissante (ex. LPM0001, LPM0002…).

    Basé sur le plus grand suffixe numérique existant + 1, donc strictement croissant.
    """
    from django.conf import settings
    prefix = getattr(settings, "LPM_MATRICULE_PREFIX", "LPM")
    nums = [
        int(m[len(prefix):])
        for m in Employee.objects.values_list("matricule", flat=True)
        if m and m.startswith(prefix) and m[len(prefix):].isdigit()
    ]
    n = (max(nums) + 1) if nums else 1
    candidate = f"{prefix}{n:04d}"
    while Employee.objects.filter(matricule=candidate).exists():
        n += 1
        candidate = f"{prefix}{n:04d}"
    return candidate


def attach_new_relations(employee, dept_names=(), position_titles=()):
    """Crée à la volée les départements/postes saisis et les rattache à l'employé."""
    for name in dept_names:
        name = (name or "").strip()
        if name:
            dep, _ = Department.objects.get_or_create(name=name)
            employee.departments.add(dep)
    for title in position_titles:
        title = (title or "").strip()
        if title:
            pos = Position.objects.filter(title__iexact=title).first() \
                or Position.objects.create(title=title)
            employee.positions.add(pos)


# --------------------------------------------------------------------------- #
# Cloisonnement par département (projets, tâches…) : chaque département gère son
# périmètre. Un responsable comme son équipe ne voient que leur département ;
# seuls RH/CEO/admin ont la vision d'ensemble.
# --------------------------------------------------------------------------- #
def department_ids_for(user):
    """Départements auxquels l'utilisateur appartient (fiche) ou qu'il dirige."""
    ids = set()
    emp = Employee.objects.filter(user=user).first()
    if emp:
        ids.update(emp.departments.values_list("id", flat=True))
    ids.update(Department.objects.filter(manager=user).values_list("id", flat=True))
    return ids


def department_colleagues_ids(user):
    """IDs des utilisateurs partageant au moins un département avec `user` (+ lui-même).

    Si l'utilisateur n'a aucun département, renvoie uniquement son propre id.
    """
    dept_ids = department_ids_for(user)
    ids = {user.id}
    if dept_ids:
        ids.update(
            Employee.objects.filter(departments__in=dept_ids)
            .values_list("user_id", flat=True)
        )
    return ids


def _norm_kw(s):
    """Minuscule sans accents (pour comparer nom/code de département de façon robuste)."""
    import unicodedata
    s = "" if s in (None, "") else str(s).strip().lower()
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def in_department(user, *keywords):
    """L'utilisateur relève-t-il d'un département dont le NOM ou le CODE contient
    l'un des mots-clés ? RH / CEO / admin ont toujours accès (vue transverse).

    Sert à réserver l'écriture d'un module au département concerné (ex. magasin →
    Logistique, finance → Financier) ; les autres internes restent en lecture.
    """
    if getattr(user, "is_rh", False):  # RH / CEO / admin
        return True
    kws = [_norm_kw(k) for k in keywords if k]
    if not kws:
        return False
    dept_ids = department_ids_for(user)
    if not dept_ids:
        return False
    for d in Department.objects.filter(id__in=dept_ids):
        hay = _norm_kw(d.name) + " " + _norm_kw(d.code)
        if any(k in hay for k in kws):
            return True
    return False
