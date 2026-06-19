"""Vues RH : hub, contrats, présences/pointage, recrutement, évaluations."""

from django.conf import settings
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from accounts.models import Role
from accounts.utils import internal_required, role_required
from employees.models import Employee

from .forms import (
    CandidateForm, ContractForm, EvaluationForm, InterviewForm, JobOpeningForm,
    MissionForm, ObjectiveFormSet,
)
from .models import (
    Attendance, Candidate, Contract, Evaluation, JobOpening, Mission,
    OfficeLocation, PayrollSetting, SalaryAdjustment, apply_mission_to_attendance,
    attendance_minutes_late, checkout_enabled_min, ensure_absences, must_clock,
    salary_impacts, status_for_checkin,
)

rh_required = role_required(Role.RH, Role.CEO, Role.ADMIN)
mgr_required = role_required(Role.MANAGER, Role.RH, Role.CEO, Role.ADMIN)


@rh_required
def stats(request):
    """Tableau de bord statistiques RH — effectifs, absences, congés, genre."""
    from django.db.models import Avg, Count, Q
    from conges.models import LeaveRequest, solde_conges

    today = timezone.localdate()
    month_start = today.replace(day=1)

    from employees.models import WORKFORCE_STATUSES
    # Effectif = personnel présent dans l'organisation (en activité OU en congé).
    active_emps = Employee.objects.filter(status__in=WORKFORCE_STATUSES).select_related("user")
    total = active_emps.count()

    # — Effectifs par département —
    from employees.models import Department
    depts = (Department.objects.annotate(nb=Count("employees", filter=Q(employees__status__in=WORKFORCE_STATUSES)))
             .order_by("-nb"))

    # — Effectifs par type de contrat —
    from hr.models import Contract
    par_contrat = (Contract.objects.filter(is_active=True)
                   .values("type").annotate(nb=Count("id")).order_by("-nb"))
    contrat_labels = {t: l for t, l in Contract.Type.choices}

    # — Taux d'absence du mois en cours —
    total_jours_pointage = Attendance.objects.filter(
        date__gte=month_start, date__lte=today,
        employee__status=Employee.Status.ACTIVE,
    ).count()
    jours_absents = Attendance.objects.filter(
        date__gte=month_start, date__lte=today,
        employee__status=Employee.Status.ACTIVE,
        status=Attendance.Status.ABSENT,
    ).count()
    taux_absence = round(jours_absents / total_jours_pointage * 100, 1) if total_jours_pointage else 0

    # — Solde de congés moyen —
    soldes = [solde_conges(e) for e in active_emps]
    solde_moyen = round(sum(soldes) / len(soldes), 1) if soldes else 0

    # — Répartition H/F —
    from employees.models import Employee as Emp
    nb_h = active_emps.filter(gender="M").count()
    nb_f = active_emps.filter(gender="F").count()
    nb_autre = total - nb_h - nb_f

    ctx = {
        "total": total,
        "depts": depts,
        "par_contrat": [
            {"label": contrat_labels.get(r["type"], r["type"]), "nb": r["nb"]}
            for r in par_contrat
        ],
        "taux_absence": taux_absence,
        "jours_absents": jours_absents,
        "total_jours_pointage": total_jours_pointage,
        "solde_moyen": solde_moyen,
        "nb_h": nb_h,
        "nb_f": nb_f,
        "nb_autre": nb_autre,
        "mois_label": month_start.strftime("%B %Y"),
        "max_dept": depts.first().nb if depts.filter(nb__gt=0).exists() else 1,
    }
    return render(request, "hr/stats.html", ctx)


@rh_required
def set_office(request):
    """Réglage du pointage : lieu (GPS) et/ou date de début."""
    if request.method != "POST":
        return redirect("hr:attendance")
    from django.conf import settings as dj_settings
    from django.utils.dateparse import parse_date
    loc = OfficeLocation.current() or OfficeLocation()

    # --- Date de début du pointage ---
    if request.POST.get("set_start"):
        loc.start_date = parse_date(request.POST.get("start_date") or "")  # None = réinitialise
        if loc.lat is None:  # nouvel enregistrement sans GPS : valeurs par défaut
            loc.lat, loc.lng = dj_settings.LPM_OFFICE_LAT, dj_settings.LPM_OFFICE_LNG
        loc.save()
        if loc.start_date:
            messages.success(request, f"Pointage compté à partir du {loc.start_date:%d/%m/%Y}.")
        else:
            messages.info(request, "Date de début du pointage réinitialisée.")
        return redirect("hr:attendance")

    # --- Lieu de pointage (GPS) ---
    try:
        lat = float(request.POST.get("lat"))
        lng = float(request.POST.get("lng"))
        radius = int(request.POST.get("radius") or 150)
    except (TypeError, ValueError):
        messages.error(request, "Position invalide.")
        return redirect("hr:attendance")
    loc.lat, loc.lng, loc.radius_m, loc.updated_by = lat, lng, radius, request.user
    loc.save()
    messages.success(request, f"Lieu de pointage enregistré ({lat:.5f}, {lng:.5f}, rayon {radius} m).")
    return redirect("hr:attendance")


def _emp(user):
    return Employee.objects.filter(user=user).first()


# --------------------------------------------------------------------------- #
# Hub RH
# --------------------------------------------------------------------------- #
@mgr_required
def hub(request):
    today = timezone.localdate()
    ctx = {
        "nb_employes": Employee.objects.filter(
            status__in=[Employee.Status.ACTIVE, Employee.Status.LEAVE]).count(),
        "nb_contrats": Contract.objects.filter(is_active=True).count(),
        "presents_today": Attendance.objects.filter(date=today, status="PRESENT").count(),
        "openings": JobOpening.objects.filter(status=JobOpening.Status.OPEN).count(),
        "candidates": Candidate.objects.exclude(status__in=["HIRED", "REJECTED"]).count(),
        "evaluations": Evaluation.objects.count(),
    }
    return render(request, "hr/hub.html", ctx)


# --------------------------------------------------------------------------- #
# Contrats
# --------------------------------------------------------------------------- #
@rh_required
def contract_list(request):
    contracts = Contract.objects.select_related("employee__user")
    return render(request, "hr/contract_list.html", {"contracts": contracts})


@rh_required
def contract_generate(request, pk):
    """Génère le contrat de travail (PDF papier en-tête) adapté au type — RH/CEO/admin."""
    from django.http import FileResponse
    from .contract_pdf import contract_pdf
    contract = get_object_or_404(Contract.objects.select_related("employee__user"), pk=pk)
    pdf = contract_pdf(contract, signer=request.user)
    return FileResponse(pdf, as_attachment=True,
                        filename=f"contrat-{contract.type}-{contract.employee.matricule}.pdf",
                        content_type="application/pdf")


@rh_required
def contract_edit(request, pk=None):
    obj = get_object_or_404(Contract, pk=pk) if pk else None
    if request.method == "POST":
        form = ContractForm(request.POST, request.FILES, instance=obj, viewer=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Contrat enregistré.")
            return redirect("hr:contracts")
    else:
        form = ContractForm(instance=obj, viewer=request.user)
    return render(request, "hr/contract_form.html", {"form": form, "obj": obj})


# --------------------------------------------------------------------------- #
# Présences / Pointage
# --------------------------------------------------------------------------- #
@internal_required
def my_attendance(request):
    # Pointage : employés, stagiaires, responsables et RH (le CEO/admin ne pointe pas).
    if not must_clock(request.user):
        messages.info(request, "Le pointage ne vous concerne pas.")
        return redirect("dashboard:home")
    emp = _emp(request.user)
    today_rec = history = mission_today = None
    if emp:
        today = timezone.localdate()
        today_rec = Attendance.objects.filter(employee=emp, date=today).first()
        history = emp.attendances.all()[:30]
        mission_today = emp.missions.filter(start_date__lte=today, end_date__gte=today).first()
    from .models import late_threshold_min
    cfg = PayrollSetting.current()
    start_min = late_threshold_min(cfg)
    late_after = f"{start_min // 60:02d}h{start_min % 60:02d}"
    co_min = checkout_enabled_min(cfg)
    now_min = timezone.localtime().hour * 60 + timezone.localtime().minute
    return render(request, "hr/pointage.html", {
        "employee": emp, "today": today_rec, "history": history or [],
        "late_after": late_after, "mission_today": mission_today,
        "can_checkout": now_min >= co_min,
        "checkout_after": f"{co_min // 60:02d}h{co_min % 60:02d}"})


def _distance_m(lat1, lng1, lat2, lng2):
    """Distance en mètres entre deux points GPS (formule de Haversine)."""
    from math import asin, cos, radians, sin, sqrt
    r = 6371000
    p1, p2 = radians(lat1), radians(lat2)
    dlat, dlng = radians(lat2 - lat1), radians(lng2 - lng1)
    a = sin(dlat / 2) ** 2 + cos(p1) * cos(p2) * sin(dlng / 2) ** 2
    return int(2 * r * asin(sqrt(a)))


@internal_required
def clock(request, action):
    if not must_clock(request.user):
        return redirect("dashboard:home")
    emp = _emp(request.user)
    if not emp:
        messages.error(request, "Aucune fiche employé associée à votre compte.")
        return redirect("hr:pointage")
    today = timezone.localdate()
    # En mission ce jour-là : pas de pointage requis (déjà compté présent).
    if emp.missions.filter(start_date__lte=today, end_date__gte=today).exists():
        messages.info(request, "Vous êtes en mission aujourd'hui : aucun pointage requis.")
        return redirect("hr:pointage")
    rec, _ = Attendance.objects.get_or_create(employee=emp, date=today)
    now = timezone.now()
    local = timezone.localtime(now)

    if action == "in" and not rec.check_in:
        # Couche 1 : restriction par IP du bureau (si activée).
        if settings.LPM_IP_RESTRICTION and settings.LPM_OFFICE_IPS:
            from accounts.utils import get_client_ip
            ip = get_client_ip(request) or ""
            if not any(ip == a or ip.startswith(a) for a in settings.LPM_OFFICE_IPS):
                messages.error(request, "Pointage refusé : vous devez être connecté au réseau du bureau.")
                return redirect("hr:pointage")
        # Couche 2 : géolocalisation GPS (lieu calibré en base, sinon config par défaut).
        loc = OfficeLocation.current()
        off_lat = loc.lat if loc else settings.LPM_OFFICE_LAT
        off_lng = loc.lng if loc else settings.LPM_OFFICE_LNG
        radius = loc.radius_m if loc else settings.LPM_OFFICE_RADIUS_M
        lat = request.POST.get("lat")
        lng = request.POST.get("lng")
        if settings.LPM_GEOFENCE_ENABLED:
            if not lat or not lng:
                messages.error(request, "Pointage refusé : localisation non disponible. "
                                        "Autorisez la géolocalisation et réessayez depuis le bureau.")
                return redirect("hr:pointage")
            dist = _distance_m(float(lat), float(lng), off_lat, off_lng)
            rec.check_in_lat, rec.check_in_lng, rec.distance_m = float(lat), float(lng), dist
            if dist > radius:
                rec.save()
                messages.error(request, f"Pointage refusé : vous êtes à {dist} m du bureau "
                                        f"(limite {radius} m). Le pointage doit se faire sur site. "
                                        "Si vous êtes bien au bureau, demandez au RH de recalibrer le lieu de pointage.")
                return redirect("hr:pointage")
            rec.on_site = True
        rec.check_in = now
        # Après le seuil de retard (08h10 par défaut) → En retard, sinon Présent.
        rec.status = status_for_checkin(local)
        rec.save()
        messages.success(request,
                         (f"Arrivée pointée sur site ({rec.distance_m} m du bureau)." if rec.on_site
                          else "Arrivée pointée."))
    elif action == "out" and rec.check_in and not rec.check_out:
        # Le pointage de départ n'est autorisé qu'à partir de l'heure configurée (15h).
        co_min = checkout_enabled_min()
        now_min = local.hour * 60 + local.minute
        if now_min < co_min:
            messages.error(request, f"Le pointage de départ n'est possible qu'à partir de "
                                    f"{co_min // 60:02d}h{co_min % 60:02d}.")
            return redirect("hr:pointage")
        rec.check_out = now
        rec.save()
        messages.success(request, "Départ pointé.")
    return redirect("hr:pointage")


@mgr_required
def attendance_today(request):
    from django.utils.dateparse import parse_date
    day = request.GET.get("date") or timezone.localdate().isoformat()
    day_obj = parse_date(day) or timezone.localdate()
    # Génère les statuts « Absent » / « En congé » pour les employés sans pointage.
    ensure_absences(day_obj)
    records = Attendance.objects.filter(date=day_obj).select_related("employee__user")
    scope = "Tout le personnel"
    # Un responsable (non RH) ne voit que les présences de SON département.
    if not request.user.is_rh:
        records = _team_scoped(records, request.user)
        scope = "Mon département"
    return render(request, "hr/attendance_today.html", {
        "records": records, "day": day, "scope": scope,
        "office": OfficeLocation.current(), "can_set_office": request.user.is_rh,
        "can_payroll": request.user.is_rh})


def _team_scoped(qs, user):
    """Un responsable (non RH) ne voit que les présences de SON/SES département(s)."""
    if user.is_rh:
        return qs
    from employees.models import department_colleagues_ids
    return qs.filter(employee__user_id__in=department_colleagues_ids(user))


@rh_required
def birthdays(request):
    """Espace anniversaires : tous les employés, classés par date (jour/mois)."""
    today = timezone.localdate()
    emps = (Employee.objects.filter(status=Employee.Status.ACTIVE)
            .exclude(birth_date__isnull=True)
            .select_related("user").prefetch_related("departments"))
    rows = [{
        "employee": e,
        "is_today": (e.birth_date.month, e.birth_date.day) == (today.month, today.day),
    } for e in emps]
    rows.sort(key=lambda r: (r["employee"].birth_date.month, r["employee"].birth_date.day))
    return render(request, "hr/birthdays.html", {"rows": rows, "count": len(rows)})


@mgr_required
def attendance_export(request):
    """Export CSV de la feuille de présence : journalière (?date=) ou mensuelle (?month=)."""
    import csv
    from datetime import date as _date
    from django.http import HttpResponse
    from django.utils.dateparse import parse_date

    month = request.GET.get("month")
    resp = HttpResponse(content_type="text/csv; charset=utf-8-sig")
    writer = csv.writer(resp, delimiter=";")
    writer.writerow(["Date", "Employé", "Matricule", "Arrivée", "Départ", "Statut", "Retard (min)", "Sur site"])

    if month:  # mensuel : AAAA-MM
        try:
            y, m = (int(x) for x in month.split("-"))
            start = _date(y, m, 1)
        except (ValueError, TypeError):
            start = timezone.localdate().replace(day=1)
        nxt = _date(start.year + (start.month == 12), (start.month % 12) + 1, 1)
        # Génère les absences sur les jours écoulés du mois.
        d = start
        while d < nxt and d <= timezone.localdate():
            ensure_absences(d)
            d = d.fromordinal(d.toordinal() + 1)
        recs = Attendance.objects.filter(date__gte=start, date__lt=nxt)
        label = f"{start:%Y-%m}"
    else:  # journalier
        day = parse_date(request.GET.get("date") or "") or timezone.localdate()
        ensure_absences(day)
        recs = Attendance.objects.filter(date=day)
        label = f"{day:%Y-%m-%d}"

    recs = _team_scoped(recs.select_related("employee__user"), request.user).order_by("date", "employee__user__last_name")
    for r in recs:
        writer.writerow([
            r.date.strftime("%d/%m/%Y"), r.employee.full_name,
            getattr(r.employee, "matricule", ""),
            timezone.localtime(r.check_in).strftime("%H:%M") if r.check_in else "",
            timezone.localtime(r.check_out).strftime("%H:%M") if r.check_out else "",
            r.get_status_display(), attendance_minutes_late(r),
            "Oui" if r.on_site else "",
        ])
    resp["Content-Disposition"] = f'attachment; filename="presences_{label}.csv"'
    return resp


@rh_required
def payroll_impacts(request):
    """Incidences salariales (retards + absences) du mois — RH / CEO / admin.

    POST : modification du coefficient global de retenue, ou ajustement manuel
    du montant retenu par employé (override)."""
    from datetime import date as _date
    from decimal import Decimal, InvalidOperation
    month = request.GET.get("month") or request.POST.get("month")
    try:
        y, m = (int(x) for x in month.split("-")) if month else (timezone.localdate().year, timezone.localdate().month)
        start = _date(y, m, 1)
    except (ValueError, TypeError, AttributeError):
        start = timezone.localdate().replace(day=1)

    if request.method == "POST":
        if "save_coefficient" in request.POST:
            try:
                coeff = Decimal(str(request.POST.get("late_coefficient", "1")).replace(",", "."))
                coeff = max(Decimal("0"), min(coeff, Decimal("10")))
            except (InvalidOperation, ValueError):
                coeff = Decimal("1")
            ps = PayrollSetting.current()
            ps.late_coefficient = coeff
            ps.updated_by = request.user
            ps.save()
            messages.success(request, f"Coefficient de retenue mis à jour ({coeff}).")
        elif "save_adjustments" in request.POST:
            changed = 0
            for emp in salary_impacts(start):
                e = emp["employee"]
                raw = (request.POST.get(f"override_{e.id}") or "").strip().replace(" ", "").replace(",", ".")
                if raw == "":
                    # Champ vidé → on retire un éventuel ajustement (retour au calcul auto).
                    if emp["overridden"]:
                        SalaryAdjustment.objects.filter(employee=e, month=start).delete()
                        changed += 1
                    continue
                try:
                    amount = int(round(float(raw)))
                except ValueError:
                    continue
                if amount == emp["computed"] and not emp["overridden"]:
                    continue  # identique au calcul auto → inutile de créer un override
                reason = (request.POST.get(f"reason_{e.id}") or "").strip()
                SalaryAdjustment.objects.update_or_create(
                    employee=e, month=start,
                    defaults={"amount": amount, "reason": reason, "set_by": request.user})
                changed += 1
            messages.success(request, f"{changed} ajustement(s) enregistré(s).")
        return redirect(f"{reverse('hr:payroll_impacts')}?month={start:%Y-%m}")

    rows = salary_impacts(start)
    total = sum(r["deduction"] for r in rows)
    return render(request, "hr/payroll_impacts.html", {
        "rows": rows, "month": f"{start:%Y-%m}", "month_label": start.strftime("%m/%Y"),
        "total": total, "coefficient": PayrollSetting.current().late_coefficient,
        "can_edit": True})


@rh_required
def payroll_export(request):
    """Export CSV des incidences salariales pour la paie — RH / CEO / admin."""
    import csv
    from datetime import date as _date

    from django.http import HttpResponse
    month = request.GET.get("month")
    try:
        y, m = (int(x) for x in month.split("-")) if month else (timezone.localdate().year, timezone.localdate().month)
        start = _date(y, m, 1)
    except (ValueError, TypeError, AttributeError):
        start = timezone.localdate().replace(day=1)
    rows = salary_impacts(start)
    resp = HttpResponse(content_type="text/csv; charset=utf-8-sig")
    writer = csv.writer(resp, delimiter=";")
    writer.writerow(["Employé", "Matricule", "Retards", "Minutes de retard", "Absences", "Retenue (FCFA)"])
    for r in rows:
        writer.writerow([r["employee"].full_name, getattr(r["employee"], "matricule", ""),
                         r["late"], r["late_minutes"], r["absent"], r["deduction"]])
    writer.writerow([])
    writer.writerow(["TOTAL", "", "", "", "", sum(r["deduction"] for r in rows)])
    resp["Content-Disposition"] = f'attachment; filename="incidences_salariales_{start:%Y-%m}.csv"'
    return resp


def _parse_hhmm(value, default):
    """« HH:MM » → minutes depuis minuit ; renvoie `default` si invalide."""
    try:
        h, m = (int(x) for x in str(value).split(":")[:2])
        if 0 <= h <= 23 and 0 <= m <= 59:
            return h * 60 + m
    except (ValueError, AttributeError):
        pass
    return default


@rh_required
def attendance_settings(request):
    """Paramètres du pointage (loi camerounaise) : horaires, heures sup, paie.

    Singleton PayrollSetting, modifiable par RH / CEO / admin.
    """
    from decimal import Decimal, InvalidOperation

    cfg = PayrollSetting.current()

    if request.method == "POST":
        def _dec(name, default, lo, hi):
            try:
                v = Decimal(str(request.POST.get(name, default)).replace(",", "."))
            except (InvalidOperation, ValueError):
                v = Decimal(str(default))
            return max(Decimal(str(lo)), min(v, Decimal(str(hi))))

        def _int(name, default, lo, hi):
            try:
                v = int(request.POST.get(name, default))
            except (ValueError, TypeError):
                v = default
            return max(lo, min(v, hi))

        cfg.late_threshold_min = _parse_hhmm(request.POST.get("late_threshold"), 8 * 60 + 10)
        cfg.work_end_min = _parse_hhmm(request.POST.get("work_end"), 17 * 60)
        cfg.checkout_enabled_min = _parse_hhmm(request.POST.get("checkout_enabled"), 15 * 60)
        cfg.overtime_min_minutes = _int("overtime_min_minutes", 30, 0, 600)
        cfg.late_recovery_max_min = _int("late_recovery_max_min", 30, 0, 600)
        cfg.ot_rate_tier1 = _dec("ot_rate_tier1", 20, 0, 500)
        cfg.ot_rate_tier2 = _dec("ot_rate_tier2", 30, 0, 500)
        cfg.ot_rate_tier3 = _dec("ot_rate_tier3", 40, 0, 500)
        cfg.ot_rate_night = _dec("ot_rate_night", 50, 0, 500)
        cfg.ot_rate_sunday = _dec("ot_rate_sunday", 40, 0, 500)
        cfg.monthly_hours = _dec("monthly_hours", "173.33", 1, 1000)
        cfg.work_hours_per_day = _dec("work_hours_per_day", 8, 1, 24)
        cfg.late_coefficient = _dec("late_coefficient", 1, 0, 10)
        cfg.updated_by = request.user
        cfg.save()
        messages.success(request, "Paramètres de pointage enregistrés.")
        return redirect("hr:attendance_settings")

    return render(request, "hr/attendance_settings.html", {"cfg": cfg})


# --------------------------------------------------------------------------- #
# Missions — enregistrées par RH / CEO / admin
# --------------------------------------------------------------------------- #
@rh_required
def mission_list(request):
    missions = Mission.objects.select_related("employee__user", "created_by").all()
    return render(request, "hr/mission_list.html", {
        "missions": missions, "today": timezone.localdate()})


@rh_required
def mission_create(request):
    if request.method == "POST":
        form = MissionForm(request.POST, viewer=request.user)
        if form.is_valid():
            mission = form.save(commit=False)
            mission.created_by = request.user
            mission.save()
            # Marque « En mission » les jours déjà écoulés/en cours.
            apply_mission_to_attendance(mission)
            # Notifie la personne concernée + informe tout le personnel.
            from notifications.models import Notification, notify, notify_internal_staff
            target = getattr(mission.employee, "user", None)
            lieu = f" à {mission.destination}" if mission.destination else ""
            periode = f"du {mission.start_date:%d/%m/%Y} au {mission.end_date:%d/%m/%Y}"
            if target:
                notify(target, "Mission enregistrée",
                       f"Vous êtes en mission{lieu} {periode}. "
                       "Votre ordre de mission est téléchargeable.",
                       Notification.Level.INFO, reverse("hr:mission_pdf", args=[mission.pk]))
            # Annonce à tout le personnel (sauf l'intéressé, déjà notifié).
            notify_internal_staff(
                "Personnel en mission",
                f"{mission.employee.full_name} est en mission{lieu} {periode}.",
                Notification.Level.INFO, reverse("conges:absences"),
                exclude=target)
            messages.success(request, "Mission enregistrée. Le personnel a été informé.")
            return redirect("hr:missions")
    else:
        form = MissionForm(viewer=request.user)
    return render(request, "hr/mission_form.html", {"form": form})


@internal_required
def mission_pdf(request, pk):
    """Ordre de mission (PDF) — accessible au RH/CEO/admin et à la personne concernée."""
    from django.core.exceptions import PermissionDenied
    from django.http import FileResponse
    from .mission_pdf import mission_order_pdf, mission_reference
    mission = get_object_or_404(Mission.objects.select_related("employee__user", "created_by"), pk=pk)
    if not (request.user.is_rh or mission.employee.user_id == request.user.id):
        raise PermissionDenied("Accès réservé à la personne concernée et au service RH.")
    pdf = mission_order_pdf(mission)
    return FileResponse(pdf, as_attachment=True,
                        filename=f"{mission_reference(mission)}.pdf",
                        content_type="application/pdf")


@rh_required
def mission_delete(request, pk):
    mission = get_object_or_404(Mission, pk=pk)
    if request.method == "POST":
        nxt = request.POST.get("next")
        mission.delete()
        messages.success(request, "Mission supprimée.")
        return redirect(nxt or "hr:missions")
    return render(request, "hr/mission_confirm_delete.html", {"mission": mission})


# --------------------------------------------------------------------------- #
# Recrutement
# --------------------------------------------------------------------------- #
@mgr_required
def opening_list(request):
    return render(request, "hr/opening_list.html", {"openings": JobOpening.objects.all()})


@rh_required
def opening_edit(request, pk=None):
    obj = get_object_or_404(JobOpening, pk=pk) if pk else None
    if request.method == "POST":
        form = JobOpeningForm(request.POST, instance=obj)
        if form.is_valid():
            o = form.save(commit=False)
            if not obj:
                o.created_by = request.user
            o.save()
            messages.success(request, "Offre enregistrée.")
            return redirect("hr:opening_detail", pk=o.pk)
    else:
        form = JobOpeningForm(instance=obj)
    return render(request, "hr/opening_form.html", {"form": form, "obj": obj})


@mgr_required
def opening_detail(request, pk):
    opening = get_object_or_404(JobOpening, pk=pk)
    if request.method == "POST":
        form = CandidateForm(request.POST, request.FILES)
        if form.is_valid():
            c = form.save(commit=False)
            c.opening = opening
            c.save()
            messages.success(request, "Candidature ajoutée.")
            return redirect("hr:opening_detail", pk=pk)
    else:
        form = CandidateForm()
    return render(request, "hr/opening_detail.html", {
        "opening": opening, "candidates": opening.candidates.all(), "form": form})


@mgr_required
def candidate_detail(request, pk):
    candidate = get_object_or_404(Candidate.objects.select_related("opening"), pk=pk)
    if request.method == "POST":
        form = InterviewForm(request.POST, viewer=request.user)
        if form.is_valid():
            it = form.save(commit=False)
            it.candidate = candidate
            it.save()
            if candidate.status in [Candidate.Status.NEW, Candidate.Status.SHORTLIST]:
                candidate.status = Candidate.Status.INTERVIEW
                candidate.save(update_fields=["status"])
            messages.success(request, "Entretien planifié.")
            return redirect("hr:candidate_detail", pk=pk)
    else:
        form = InterviewForm(initial={"interviewer": request.user}, viewer=request.user)
    return render(request, "hr/candidate_detail.html", {
        "candidate": candidate, "interviews": candidate.interviews.select_related("interviewer"), "form": form})


@mgr_required
def candidate_status(request, pk, status):
    candidate = get_object_or_404(Candidate, pk=pk)
    if status in Candidate.Status.values:
        candidate.status = status
        candidate.save(update_fields=["status"])
        messages.success(request, "Statut de la candidature mis à jour.")
    return redirect("hr:candidate_detail", pk=pk)


# --------------------------------------------------------------------------- #
# Évaluation / Performance
# --------------------------------------------------------------------------- #
def _can_eval(user, ev):
    """RH/CEO/admin : toutes les évaluations. Responsable : son département (hors lui-même)."""
    if user.is_rh:
        return True
    from employees.models import department_colleagues_ids
    return (ev.employee.user_id in department_colleagues_ids(user)
            and ev.employee.user_id != user.id)


@mgr_required
def evaluation_list(request):
    evals = Evaluation.objects.select_related("employee__user", "evaluator")
    if not request.user.is_rh:  # responsable → uniquement son département
        from employees.models import department_colleagues_ids
        evals = (evals.filter(employee__user_id__in=department_colleagues_ids(request.user))
                 .exclude(employee__user=request.user))
    return render(request, "hr/evaluation_list.html", {"evaluations": evals})


@mgr_required
def evaluation_edit(request, pk=None):
    ev = get_object_or_404(Evaluation, pk=pk) if pk else None
    if ev and not _can_eval(request.user, ev):
        messages.error(request, "Vous ne pouvez évaluer que les membres de votre équipe.")
        return redirect("hr:evaluations")
    if request.method == "POST":
        form = EvaluationForm(request.POST, instance=ev, viewer=request.user)
        formset = ObjectiveFormSet(request.POST, instance=ev)
        if form.is_valid() and formset.is_valid():
            obj = form.save(commit=False)
            if not ev:
                obj.evaluator = request.user
            obj.save()
            formset.instance = obj
            formset.save()
            messages.success(request, "Évaluation enregistrée.")
            return redirect("hr:evaluation_detail", pk=obj.pk)
    else:
        form = EvaluationForm(instance=ev, viewer=request.user)
        formset = ObjectiveFormSet(instance=ev)
    return render(request, "hr/evaluation_form.html", {"form": form, "formset": formset, "ev": ev})


@mgr_required
def evaluation_detail(request, pk):
    ev = get_object_or_404(Evaluation.objects.select_related("employee__user", "evaluator"), pk=pk)
    if not _can_eval(request.user, ev):
        messages.error(request, "Vous ne pouvez consulter que les évaluations de votre équipe.")
        return redirect("hr:evaluations")
    return render(request, "hr/evaluation_detail.html", {"ev": ev})


@mgr_required
def evaluation_status(request, pk, status):
    ev = get_object_or_404(Evaluation, pk=pk)
    if not _can_eval(request.user, ev):
        messages.error(request, "Action non autorisée.")
        return redirect("hr:evaluations")
    if status in Evaluation.Status.values:
        ev.status = status
        ev.save(update_fields=["status"])
        messages.success(request, "Statut mis à jour.")
    return redirect("hr:evaluation_detail", pk=pk)


# ---------------------------------------------------------------------------
# Onboarding
# ---------------------------------------------------------------------------
@rh_required
def onboarding_list(request):
    from .models import OnboardingPlan, OnboardingProgress
    plans = OnboardingPlan.objects.prefetch_related("steps").all()
    in_progress = OnboardingProgress.objects.select_related("employee__user", "plan").order_by("-started_at")[:10]
    return render(request, "hr/onboarding_list.html", {"plans": plans, "in_progress": in_progress})


@rh_required
def onboarding_plan_edit(request, pk=None):
    from .models import OnboardingPlan
    from .forms import OnboardingPlanForm
    obj = get_object_or_404(OnboardingPlan, pk=pk) if pk else None
    if request.method == "POST":
        form = OnboardingPlanForm(request.POST, instance=obj)
        if form.is_valid():
            p = form.save(commit=False)
            if not obj:
                p.created_by = request.user
            p.save()
            messages.success(request, "Plan d'intégration enregistré.")
            return redirect("hr:onboarding")
    else:
        form = OnboardingPlanForm(instance=obj)
    return render(request, "hr/onboarding_form.html", {"form": form, "obj": obj})
