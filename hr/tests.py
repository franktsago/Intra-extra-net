from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Role, User
from employees.models import Employee
from hr.models import Attendance, ensure_absences


class HireDateContractSyncTest(TestCase):
    """Date d'embauche ↔ date de début du contrat actif restent égales (items 1 & 2)."""

    @classmethod
    def setUpTestData(cls):
        from datetime import date
        cls.rh = User.objects.create_user("rh_sync", password="x", role=Role.RH)
        cls.u = User.objects.create_user("e.sync", password="x", role=Role.EMPLOYE,
                                         first_name="Eva", last_name="SYNC", email="e@lpm.cm")
        cls.emp = Employee.objects.get(user=cls.u)
        cls.emp.hire_date = date(2023, 3, 1)
        cls.emp.save(update_fields=["hire_date"])

    def test_contract_save_updates_hire_date(self):
        from datetime import date
        from hr.models import Contract
        from hr.forms import ContractForm
        form = ContractForm(data={
            "employee": self.emp.pk, "type": "CDI", "start_date": "2022-09-15",
            "salary": "300000", "probation_months": "0", "pay_day": "30",
            "nationality": "Camerounaise", "is_active": "on",
            "transport_allowance": "0", "housing_allowance": "0",
            "performance_allowance": "0",
        }, viewer=self.rh)
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.emp.refresh_from_db()
        self.assertEqual(self.emp.hire_date, date(2022, 9, 15))

    def test_employee_edit_updates_active_contract(self):
        from datetime import date
        from hr.models import Contract
        contract = Contract.objects.create(
            employee=self.emp, type=Contract.Type.CDI,
            start_date=date(2023, 3, 1), is_active=True, salary=300000)
        self.client.force_login(self.rh)
        r = self.client.post(reverse("employees:edit", args=[self.emp.pk]), {
            "gender": "F", "hire_date": "2021-01-04",
            "first_name": "Eva", "last_name": "SYNC", "email": "e@lpm.cm", "phone": "",
            "contract_type": "CDI", "status": "ACTIVE", "city": "Douala",
            "emergency_contact": "X", "emergency_contact_phone": "+237 699000000",
        })
        self.assertEqual(r.status_code, 302)
        self.emp.refresh_from_db()
        contract.refresh_from_db()
        self.assertEqual(self.emp.hire_date, date(2021, 1, 4))
        self.assertEqual(contract.start_date, date(2021, 1, 4))  # contrat aligné

    def test_hire_date_persists_on_edit(self):
        """Item 1 : la date d'embauche saisie est bien conservée après modification."""
        from datetime import date
        self.client.force_login(self.rh)
        self.client.post(reverse("employees:edit", args=[self.emp.pk]), {
            "gender": "F", "hire_date": "2020-06-30",
            "first_name": "Eva", "last_name": "SYNC", "email": "e@lpm.cm", "phone": "",
            "contract_type": "CDI", "status": "ACTIVE", "city": "Douala",
            "emergency_contact": "X", "emergency_contact_phone": "+237 699000000",
        })
        self.emp.refresh_from_db()
        self.assertEqual(self.emp.hire_date, date(2020, 6, 30))


class PointageAccessTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.mgr = User.objects.create_user("mgr", password="x", role=Role.MANAGER)
        cls.rh = User.objects.create_user("rh", password="x", role=Role.RH)
        cls.ceo = User.objects.create_user("ceo", password="x", role=Role.CEO)
        cls.emp = User.objects.create_user("emp", password="x", role=Role.EMPLOYE)
        cls.stg = User.objects.create_user("stg", password="x", role=Role.STAGIAIRE)

    def test_pointage_visible_for_employee_stagiaire_manager_rh(self):
        for u in (self.emp, self.stg, self.mgr, self.rh):
            self.client.force_login(u)
            dash = self.client.get(reverse("dashboard:home")).content.decode("utf-8", "ignore")
            self.assertIn("/rh/pointage", dash, f"{u.username} devrait voir le pointage")
            self.assertEqual(self.client.get(reverse("hr:pointage")).status_code, 200)

    def test_pointage_hidden_and_blocked_for_ceo(self):
        self.client.force_login(self.ceo)
        dash = self.client.get(reverse("dashboard:home")).content.decode("utf-8", "ignore")
        self.assertNotIn("/rh/pointage", dash)
        self.assertEqual(self.client.get(reverse("hr:pointage")).status_code, 302)


class AttendanceStartDateTest(TestCase):
    """Le pointage ne compte qu'à partir de la date de début (présences + paie)."""

    def test_absences_skip_days_before_start(self):
        from hr.models import Attendance, OfficeLocation, ensure_absences
        from employees.models import Employee
        u = User.objects.create_user("att_gate", password="x", role=Role.EMPLOYE)
        emp = Employee.objects.get(user=u)
        today = timezone.localdate()
        start = today - timedelta(days=3)
        OfficeLocation.objects.create(name="S", lat=1.0, lng=1.0, start_date=start)
        before = today - timedelta(days=5)
        after = today - timedelta(days=2)
        ensure_absences(before)
        ensure_absences(after)
        self.assertFalse(Attendance.objects.filter(employee=emp, date=before).exists())
        self.assertTrue(Attendance.objects.filter(employee=emp, date=after).exists())

    def test_salary_impacts_ignore_days_before_start(self):
        from datetime import date
        from hr.models import Attendance, Contract, OfficeLocation, salary_impacts
        from employees.models import Employee
        u = User.objects.create_user("att_sal", password="x", role=Role.EMPLOYE)
        emp = Employee.objects.get(user=u)
        Contract.objects.create(employee=emp, type=Contract.Type.CDI,
                                start_date=date(2026, 1, 1), is_active=True, salary=300000)
        OfficeLocation.objects.create(name="S", lat=1.0, lng=1.0, start_date=date(2026, 1, 15))
        Attendance.objects.create(employee=emp, date=date(2026, 1, 5), status=Attendance.Status.ABSENT)
        Attendance.objects.create(employee=emp, date=date(2026, 1, 20), status=Attendance.Status.ABSENT)
        rows = salary_impacts(date(2026, 1, 1), employees=[emp])
        self.assertEqual(rows[0]["absent"], 1)  # seul le 20/01 (≥ début) est compté


class AbsenceGenerationTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.mgr = User.objects.create_user("mgr", password="x", role=Role.MANAGER)
        cls.rh = User.objects.create_user("rhabs", password="x", role=Role.RH)
        cls.ceo = User.objects.create_user("ceoabs", password="x", role=Role.CEO)
        cls.emp = User.objects.create_user("emp", password="x", role=Role.EMPLOYE)
        cls.stg = User.objects.create_user("stg", password="x", role=Role.STAGIAIRE)

    def test_absences_only_for_clocking_roles(self):
        yesterday = timezone.localdate() - timedelta(days=1)
        ensure_absences(yesterday)
        # Employés, stagiaires, responsables et RH pointent → absence générée.
        for u in (self.emp, self.stg, self.mgr, self.rh):
            emp = Employee.objects.get(user=u)
            self.assertEqual(Attendance.objects.get(employee=emp, date=yesterday).status,
                             "ABSENT", f"{u.username} devrait être marqué absent")
        # Le CEO/admin ne pointe pas → aucune présence générée.
        emp_ceo = Employee.objects.get(user=self.ceo)
        self.assertFalse(Attendance.objects.filter(employee=emp_ceo, date=yesterday).exists())

    def test_existing_record_not_overwritten(self):
        yesterday = timezone.localdate() - timedelta(days=1)
        emp_e = Employee.objects.get(user=self.emp)
        Attendance.objects.create(employee=emp_e, date=yesterday, status=Attendance.Status.PRESENT)
        ensure_absences(yesterday)
        self.assertEqual(Attendance.objects.get(employee=emp_e, date=yesterday).status, "PRESENT")

    def test_future_day_no_absence(self):
        tomorrow = timezone.localdate() + timedelta(days=1)
        ensure_absences(tomorrow)
        self.assertEqual(Attendance.objects.filter(date=tomorrow).count(), 0)

    def test_on_leave_employee_shown_in_pointage(self):
        """Un employé en congé reste visible dans la feuille de présence, marqué
        « En congé » — il n'est pas masqué."""
        from conges.models import LeaveRequest, LeaveType
        yesterday = timezone.localdate() - timedelta(days=1)
        emp = Employee.objects.get(user=self.emp)
        # Congé approuvé couvrant hier + statut « En congé ».
        lt = LeaveType.objects.create(name="Congé annuel", code="ANN")
        LeaveRequest.objects.create(
            employee=emp, leave_type=lt,
            start_date=yesterday - timedelta(days=1), end_date=yesterday + timedelta(days=1),
            status=LeaveRequest.Status.APPROVED)
        emp.status = Employee.Status.LEAVE
        emp.save(update_fields=["status"])
        ensure_absences(yesterday)
        rec = Attendance.objects.get(employee=emp, date=yesterday)
        self.assertEqual(rec.status, Attendance.Status.LEAVE)  # visible « En congé »


class AttendanceDepartmentScopeTest(TestCase):
    """Présences cloisonnées par département : un responsable voit son département."""

    @classmethod
    def setUpTestData(cls):
        from employees.models import Department, Employee
        cls.mkt = Department.objects.create(name="Marketing", code="MKT")
        cls.fin = Department.objects.create(name="Finance", code="FIN")
        cls.mgr = User.objects.create_user("mgr_att", password="x", role=Role.MANAGER,
                                           first_name="Manon", last_name="CHEFMKT")
        cls.member = User.objects.create_user("mem_att", password="x", role=Role.EMPLOYE,
                                              first_name="Mike", last_name="MKTMEMBER")
        cls.other = User.objects.create_user("oth_att", password="x", role=Role.EMPLOYE,
                                             first_name="Otto", last_name="FINMEMBER")
        Employee.objects.get(user=cls.mgr).departments.set([cls.mkt])
        Employee.objects.get(user=cls.member).departments.set([cls.mkt])
        Employee.objects.get(user=cls.other).departments.set([cls.fin])

    def test_manager_sees_only_department_attendance(self):
        from hr.models import Attendance
        from employees.models import Employee
        today = timezone.localdate()
        Attendance.objects.create(employee=Employee.objects.get(user=self.member),
                                  date=today, status=Attendance.Status.PRESENT)
        Attendance.objects.create(employee=Employee.objects.get(user=self.other),
                                  date=today, status=Attendance.Status.PRESENT)
        self.client.force_login(self.mgr)
        r = self.client.get(reverse("hr:attendance") + f"?date={today.isoformat()}")
        self.assertContains(r, "MKTMEMBER")       # membre de son département
        self.assertNotContains(r, "FINMEMBER")    # autre département

    def test_rh_sees_everyone(self):
        from hr.models import Attendance
        from employees.models import Employee
        rh = User.objects.create_user("rh_att", password="x", role=Role.RH)
        today = timezone.localdate()
        Attendance.objects.create(employee=Employee.objects.get(user=self.member),
                                  date=today, status=Attendance.Status.PRESENT)
        Attendance.objects.create(employee=Employee.objects.get(user=self.other),
                                  date=today, status=Attendance.Status.PRESENT)
        self.client.force_login(rh)
        r = self.client.get(reverse("hr:attendance") + f"?date={today.isoformat()}")
        self.assertContains(r, "MKTMEMBER")
        self.assertContains(r, "FINMEMBER")


class EvaluationTeamTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        from employees.models import Department, Employee
        cls.mkt = Department.objects.create(name="Marketing", code="MKT")
        cls.fin = Department.objects.create(name="Finance", code="FIN")
        cls.mgr = User.objects.create_user("evmgr", password="x", role=Role.MANAGER)
        cls.member = User.objects.create_user("evmember", password="x", role=Role.EMPLOYE)
        cls.outsider = User.objects.create_user("evout", password="x", role=Role.EMPLOYE)
        Employee.objects.get(user=cls.mgr).departments.set([cls.mkt])
        Employee.objects.get(user=cls.member).departments.set([cls.mkt])
        Employee.objects.get(user=cls.outsider).departments.set([cls.fin])

    def test_manager_evaluates_only_department(self):
        from hr.forms import EvaluationForm
        ids = set(EvaluationForm(viewer=self.mgr).fields["employee"].queryset.values_list("user_id", flat=True))
        self.assertIn(self.member.id, ids)          # membre de son département
        self.assertNotIn(self.outsider.id, ids)     # autre département
        self.assertNotIn(self.mgr.id, ids)          # pas lui-même


class LateThresholdTest(TestCase):
    """Seuil de retard fixé à 08h10 + retenue au prorata des minutes de retard."""

    def _aware(self, h, m):
        from datetime import datetime, time
        return timezone.make_aware(datetime.combine(timezone.localdate(), time(h, m)))

    def test_threshold_is_810(self):
        from django.conf import settings
        self.assertEqual(settings.LPM_WORK_START_MIN, 8 * 60 + 10)

    def test_status_present_until_810_then_late(self):
        from hr.models import Attendance, status_for_checkin
        self.assertEqual(status_for_checkin(self._aware(8, 0)), Attendance.Status.PRESENT)   # 08h00
        self.assertEqual(status_for_checkin(self._aware(8, 9)), Attendance.Status.PRESENT)   # 08h09
        self.assertEqual(status_for_checkin(self._aware(8, 10)), Attendance.Status.PRESENT)  # 08h10 pile = à l'heure
        self.assertEqual(status_for_checkin(self._aware(8, 11)), Attendance.Status.LATE)     # 08h11 = en retard
        self.assertEqual(status_for_checkin(self._aware(8, 25)), Attendance.Status.LATE)     # 08h25 = en retard

    def test_minutes_late_measured_from_810(self):
        from hr.models import Attendance, attendance_minutes_late
        emp_user = User.objects.create_user("lateemp", password="x", role=Role.EMPLOYE)
        emp = Employee.objects.get(user=emp_user)
        rec = Attendance.objects.create(employee=emp, date=timezone.localdate(),
                                        status=Attendance.Status.LATE, check_in=self._aware(8, 25))
        self.assertEqual(attendance_minutes_late(rec), 15)  # 08h25 − 08h10 = 15 min

    def test_prorata_deduction_on_lateness(self):
        from datetime import date
        from hr.models import Attendance, Contract, salary_impacts
        emp_user = User.objects.create_user("prorata", password="x", role=Role.EMPLOYE)
        emp = Employee.objects.get(user=emp_user)
        # Salaire 173 330 → taux horaire = 1000 F/h.
        Contract.objects.create(employee=emp, type=Contract.Type.CDI,
                                start_date=date(2026, 1, 1), salary=173330, is_active=True)
        month_start = timezone.localdate().replace(day=1)
        # Arrivée à 08h40 = 30 min de retard → 1000 × (30/60) = 500 F.
        Attendance.objects.create(employee=emp, date=month_start,
                                  status=Attendance.Status.LATE, check_in=self._aware(8, 40))
        row = {r["employee"].id: r for r in salary_impacts(month_start)}[emp.id]
        self.assertEqual(row["late"], 1)
        self.assertEqual(row["late_minutes"], 30)
        self.assertEqual(row["deduction"], 500)


class SalaryImpactTest(TestCase):
    def test_deduction_for_absence_and_lateness(self):
        from datetime import date, timedelta
        from django.utils import timezone
        from hr.models import Attendance, salary_impacts
        from hr.models import Contract
        emp_user = User.objects.create_user("payemp", password="x", role=Role.EMPLOYE)
        emp = Employee.objects.get(user=emp_user)
        # Salaire 173 330 → taux horaire = 1000 F/h (173.33 h légales).
        Contract.objects.create(employee=emp, type=Contract.Type.CDI,
                                start_date=date(2026, 1, 1), salary=173330, is_active=True)
        month_start = timezone.localdate().replace(day=1)
        d = month_start
        # Une absence = 8 h × 1000 = 8000 F de retenue.
        Attendance.objects.create(employee=emp, date=d, status=Attendance.Status.ABSENT)
        rows = {r["employee"].id: r for r in salary_impacts(month_start)}
        self.assertIn(emp.id, rows)
        self.assertEqual(rows[emp.id]["absent"], 1)
        self.assertEqual(rows[emp.id]["deduction"], 8000)


class MissionTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.rh = User.objects.create_user("rhmiss", password="x", role=Role.RH)
        cls.emp_user = User.objects.create_user("missemp", password="x", role=Role.EMPLOYE)
        cls.emp = Employee.objects.get(user=cls.emp_user)

    def test_only_rh_can_access_missions(self):
        self.client.force_login(self.emp_user)
        self.assertEqual(self.client.get(reverse("hr:missions")).status_code, 403)
        self.client.force_login(self.rh)
        self.assertEqual(self.client.get(reverse("hr:missions")).status_code, 200)

    def test_rh_creates_mission_marks_employee_on_mission(self):
        from datetime import timedelta
        from hr.models import Attendance, ensure_absences
        start = timezone.localdate() - timedelta(days=1)
        end = timezone.localdate()
        self.client.force_login(self.rh)
        r = self.client.post(reverse("hr:mission_create"), {
            "employee": self.emp.pk, "start_date": start.isoformat(),
            "end_date": end.isoformat(), "destination": "Yaoundé", "objet": "Rendez-vous client",
        })
        self.assertEqual(r.status_code, 302)
        # Le jour passé de la mission est marqué « En mission » (pas absent).
        rec = Attendance.objects.get(employee=self.emp, date=start)
        self.assertEqual(rec.status, Attendance.Status.MISSION)
        # ensure_absences ne doit pas le repasser en absent.
        ensure_absences(start)
        rec.refresh_from_db()
        self.assertEqual(rec.status, Attendance.Status.MISSION)
        # La personne est notifiée.
        from notifications.models import Notification
        self.assertTrue(Notification.objects.filter(
            recipient=self.emp_user, title__icontains="mission").exists())

    def test_mission_notifies_all_staff(self):
        bystander = User.objects.create_user("temoinmiss", password="x", role=Role.EMPLOYE)
        self.client.force_login(self.rh)
        self.client.post(reverse("hr:mission_create"), {
            "employee": self.emp.pk, "start_date": timezone.localdate().isoformat(),
            "end_date": timezone.localdate().isoformat(), "destination": "Douala",
        })
        from notifications.models import Notification
        # Un collègue non concerné est informé de la mission.
        self.assertTrue(Notification.objects.filter(
            recipient=bystander, title__icontains="mission").exists())
        # L'intéressé reçoit sa notif personnelle, pas l'annonce générale en double.
        self.assertEqual(Notification.objects.filter(
            recipient=self.emp_user, title__icontains="mission").count(), 1)

    def test_mission_order_pdf_download(self):
        from hr.models import Mission
        m = Mission.objects.create(employee=self.emp, start_date=timezone.localdate(),
                                   end_date=timezone.localdate(), destination="Kribi",
                                   created_by=self.rh)
        url = reverse("hr:mission_pdf", args=[m.pk])
        # La personne concernée peut télécharger son ordre de mission.
        self.client.force_login(self.emp_user)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"], "application/pdf")
        # La RH aussi.
        self.client.force_login(self.rh)
        self.assertEqual(self.client.get(url).status_code, 200)
        # Un tiers non concerné est refusé.
        other = User.objects.create_user("tiers", password="x", role=Role.EMPLOYE)
        self.client.force_login(other)
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_mission_blocks_clocking(self):
        from hr.models import Mission
        Mission.objects.create(employee=self.emp, start_date=timezone.localdate(),
                               end_date=timezone.localdate(), created_by=self.rh)
        self.client.force_login(self.emp_user)
        self.client.post(reverse("hr:clock", args=["in"]), {"lat": "4.07424", "lng": "9.71709"})
        from hr.models import Attendance
        rec = Attendance.objects.filter(employee=self.emp, date=timezone.localdate()).first()
        # Aucun pointage d'arrivée enregistré (mission).
        self.assertTrue(rec is None or rec.check_in is None)


class ProrataEditTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        from datetime import date
        from hr.models import Contract
        cls.rh = User.objects.create_user("rhpay", password="x", role=Role.RH)
        cls.emp_user = User.objects.create_user("payedit", password="x", role=Role.EMPLOYE)
        cls.emp = Employee.objects.get(user=cls.emp_user)
        Contract.objects.create(employee=cls.emp, type=Contract.Type.CDI,
                                start_date=date(2026, 1, 1), salary=173330, is_active=True)

    def _aware(self, h, m):
        from datetime import datetime, time
        return timezone.make_aware(datetime.combine(timezone.localdate(), time(h, m)))

    def test_global_coefficient_scales_late_deduction(self):
        from hr.models import Attendance, PayrollSetting, salary_impacts
        month_start = timezone.localdate().replace(day=1)
        # 30 min de retard → 500 F au coefficient 1.
        Attendance.objects.create(employee=self.emp, date=month_start,
                                  status=Attendance.Status.LATE, check_in=self._aware(8, 40))
        self.client.force_login(self.rh)
        self.client.post(reverse("hr:payroll_impacts"), {
            "save_coefficient": "1", "late_coefficient": "0.5",
            "month": f"{month_start:%Y-%m}"})
        self.assertEqual(PayrollSetting.current().late_coefficient, __import__("decimal").Decimal("0.50"))
        row = {r["employee"].id: r for r in salary_impacts(month_start)}[self.emp.id]
        self.assertEqual(row["deduction"], 250)  # 500 × 0,5

    def test_manual_override_forces_amount(self):
        from hr.models import Attendance, SalaryAdjustment, salary_impacts
        month_start = timezone.localdate().replace(day=1)
        Attendance.objects.create(employee=self.emp, date=month_start,
                                  status=Attendance.Status.LATE, check_in=self._aware(8, 40))
        self.client.force_login(self.rh)
        # Force la retenue à 100 F (au lieu de 500 calculés).
        self.client.post(reverse("hr:payroll_impacts"), {
            "save_adjustments": "1", "month": f"{month_start:%Y-%m}",
            f"override_{self.emp.id}": "100", f"reason_{self.emp.id}": "Retard justifié"})
        self.assertTrue(SalaryAdjustment.objects.filter(employee=self.emp, month=month_start).exists())
        row = {r["employee"].id: r for r in salary_impacts(month_start)}[self.emp.id]
        self.assertEqual(row["computed"], 500)
        self.assertEqual(row["deduction"], 100)
        self.assertTrue(row["overridden"])
        # Vider le champ → retour au calcul auto.
        self.client.post(reverse("hr:payroll_impacts"), {
            "save_adjustments": "1", "month": f"{month_start:%Y-%m}",
            f"override_{self.emp.id}": ""})
        row = {r["employee"].id: r for r in salary_impacts(month_start)}[self.emp.id]
        self.assertEqual(row["deduction"], 500)
        self.assertFalse(row["overridden"])

    def test_employee_cannot_edit_prorata(self):
        self.client.force_login(self.emp_user)
        self.assertEqual(self.client.get(reverse("hr:payroll_impacts")).status_code, 403)


class ContractGenerationTest(TestCase):
    """Génération du contrat (PDF) pour tous les types — RH/CEO/admin uniquement."""

    @classmethod
    def setUpTestData(cls):
        from datetime import date
        from hr.models import Contract
        cls.rh = User.objects.create_user("rhgen", password="x", role=Role.RH)
        cls.emp_user = User.objects.create_user("genemp", password="x", role=Role.EMPLOYE)
        cls.emp = Employee.objects.get(user=cls.emp_user)
        cls.contracts = {}
        for t in (Contract.Type.CDI, Contract.Type.CDD, Contract.Type.STAGE, Contract.Type.TEMP):
            cls.contracts[t] = Contract.objects.create(
                employee=cls.emp, type=t, start_date=date(2026, 1, 1),
                end_date=date(2026, 12, 31), salary=200000, is_active=(t == Contract.Type.CDI))

    def test_rh_generates_all_contract_types(self):
        self.client.force_login(self.rh)
        for t, c in self.contracts.items():
            r = self.client.get(reverse("hr:contract_generate", args=[c.pk]))
            self.assertEqual(r.status_code, 200, t)
            self.assertEqual(r["Content-Type"], "application/pdf")

    def test_employee_cannot_generate(self):
        self.client.force_login(self.emp_user)
        c = self.contracts["CDI"]
        self.assertEqual(self.client.get(
            reverse("hr:contract_generate", args=[c.pk])).status_code, 403)

    def test_gross_salary_sums_allowances(self):
        c = self.contracts["CDI"]
        c.transport_allowance = 30000
        c.housing_allowance = 20000
        c.save()
        self.assertEqual(c.gross_salary, 250000)


class EndingContractNotifyTest(TestCase):
    """Fin de CDD/Stage → notification RH/CEO/admin dès 4 jours avant la fin (J-4 → J)."""

    def test_ending_contract_notifies_management_from_4_days(self):
        from datetime import timedelta
        from hr.models import Contract, notify_ending_contracts
        from notifications.models import Notification
        rh = User.objects.create_user("rhend", password="x", role=Role.RH)
        ceo = User.objects.create_user("ceoend", password="x", role=Role.CEO)
        emp = Employee.objects.get(user=User.objects.create_user("stgend", password="x", role=Role.STAGIAIRE))
        today = timezone.localdate()
        # À 4 jours de la fin → doit notifier.
        Contract.objects.create(employee=emp, type=Contract.Type.STAGE,
                                start_date=today - timedelta(days=30),
                                end_date=today + timedelta(days=4), is_active=True)
        n = notify_ending_contracts(today)
        self.assertEqual(n, 1)
        self.assertTrue(Notification.objects.filter(recipient=rh, title__icontains="stage").exists())
        self.assertTrue(Notification.objects.filter(recipient=ceo, title__icontains="stage").exists())

    def test_not_notified_before_4_days(self):
        from datetime import timedelta
        from hr.models import Contract, notify_ending_contracts
        User.objects.create_user("rhend5", password="x", role=Role.RH)
        emp = Employee.objects.get(user=User.objects.create_user("stg5", password="x", role=Role.STAGIAIRE))
        today = timezone.localdate()
        # À 5 jours → pas encore notifié.
        Contract.objects.create(employee=emp, type=Contract.Type.STAGE,
                                start_date=today - timedelta(days=30),
                                end_date=today + timedelta(days=5), is_active=True)
        self.assertEqual(notify_ending_contracts(today), 0)

    def test_cdi_not_notified(self):
        from datetime import timedelta
        from hr.models import Contract, notify_ending_contracts
        User.objects.create_user("rhend2", password="x", role=Role.RH)
        emp = Employee.objects.get(user=User.objects.create_user("cdiend", password="x", role=Role.EMPLOYE))
        today = timezone.localdate()
        Contract.objects.create(employee=emp, type=Contract.Type.CDI,
                                start_date=today, is_active=True)
        self.assertEqual(notify_ending_contracts(today), 0)


class TempContractNotifyTest(TestCase):
    """Le contrat Temporaire/Mission est aussi signalé à échéance."""

    def test_temp_contract_notifies_management(self):
        from datetime import timedelta
        from hr.models import Contract, notify_ending_contracts
        from notifications.models import Notification
        rh = User.objects.create_user("rhtmp", password="x", role=Role.RH)
        emp = Employee.objects.get(user=User.objects.create_user("tmpemp", password="x", role=Role.EMPLOYE))
        today = timezone.localdate()
        Contract.objects.create(employee=emp, type=Contract.Type.TEMP,
                                start_date=today - timedelta(days=10),
                                end_date=today + timedelta(days=1), is_active=True)
        self.assertEqual(notify_ending_contracts(today), 1)
        self.assertTrue(Notification.objects.filter(
            recipient=rh, title__icontains="mission temporaire").exists())


class OnboardingAccessTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.rh = User.objects.create_user("rh_onb", password="x", role=Role.RH)
        cls.emp = User.objects.create_user("emp_onb", password="x", role=Role.EMPLOYE)

    def test_rh_can_access_onboarding_list(self):
        self.client.force_login(self.rh)
        self.assertEqual(self.client.get(reverse("hr:onboarding")).status_code, 200)

    def test_employee_blocked_from_onboarding_list(self):
        self.client.force_login(self.emp)
        self.assertEqual(self.client.get(reverse("hr:onboarding")).status_code, 403)

    def test_rh_can_access_onboarding_create(self):
        self.client.force_login(self.rh)
        self.assertEqual(self.client.get(reverse("hr:onboarding_create")).status_code, 200)

    def test_employee_blocked_from_onboarding_create(self):
        self.client.force_login(self.emp)
        self.assertEqual(self.client.get(reverse("hr:onboarding_create")).status_code, 403)


class StatsRHTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.rh = User.objects.create_user("rh_stats", password="x", role=Role.RH)
        cls.manager = User.objects.create_user("mgr_stats", password="x", role=Role.MANAGER)

    def test_stats_200_pour_rh(self):
        self.client.force_login(self.rh)
        self.assertEqual(self.client.get(reverse("hr:stats")).status_code, 200)

    def test_stats_403_pour_manager(self):
        self.client.force_login(self.manager)
        self.assertEqual(self.client.get(reverse("hr:stats")).status_code, 403)


class EndingContractIdempotentTest(TestCase):
    """La notification de fin de contrat ne se crée qu'une fois par jour (anti-doublon)."""

    def test_no_duplicate_same_day(self):
        from datetime import timedelta
        from hr.models import Contract, notify_ending_contracts
        from notifications.models import Notification
        rh = User.objects.create_user("rhidem", password="x", role=Role.RH)
        emp = Employee.objects.get(user=User.objects.create_user("stgidem", password="x", role=Role.STAGIAIRE))
        today = timezone.localdate()
        Contract.objects.create(employee=emp, type=Contract.Type.STAGE,
                                start_date=today - timedelta(days=20),
                                end_date=today + timedelta(days=2), is_active=True)
        notify_ending_contracts(today)
        notify_ending_contracts(today)   # 2e passage le même jour
        notify_ending_contracts(today)   # 3e passage
        n = Notification.objects.filter(recipient=rh, title__icontains="stage").count()
        self.assertEqual(n, 1, "une seule notification par jour attendue")
