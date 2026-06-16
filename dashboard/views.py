"""Tableau de bord — vue d'ensemble adaptée au rôle de l'utilisateur."""

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.templatetags.static import static
from django.utils import timezone

from communication.models import Event, News
from conges.models import LeaveRequest, solde_conges
from documents.models import Document
from employees.models import Employee
from tasks.models import Task


def manifest(request):
    """Web App Manifest (PWA installable)."""
    icon = static("img/logo.png")
    return JsonResponse({
        "name": "LPM Consulting Group — Intranet",
        "short_name": "LPM",
        "description": "Plateforme intranet & extranet de LPM Consulting Group.",
        "start_url": "/",
        "scope": "/",
        "display": "standalone",
        "orientation": "portrait-primary",
        "background_color": "#0a1a33",
        "theme_color": "#0073DE",
        "lang": "fr",
        "icons": [
            {"src": icon, "sizes": "192x192", "type": "image/png", "purpose": "any maskable"},
            {"src": icon, "sizes": "512x512", "type": "image/png", "purpose": "any maskable"},
        ],
    })


def service_worker(request):
    """Service worker minimal : installabilité + cache des assets statiques."""
    js = """
const CACHE = 'lpm-v1';
self.addEventListener('install', function(e){ self.skipWaiting(); });
self.addEventListener('activate', function(e){ e.waitUntil(self.clients.claim()); });
self.addEventListener('fetch', function(e){
  if (e.request.method !== 'GET') return;
  var url = e.request.url;
  if (url.indexOf('/static/') !== -1) {
    // Assets statiques : cache-first.
    e.respondWith(
      caches.match(e.request).then(function(c){
        return c || fetch(e.request).then(function(resp){
          var cp = resp.clone();
          caches.open(CACHE).then(function(ch){ ch.put(e.request, cp); });
          return resp;
        });
      })
    );
  }
  // Le reste (pages, API) : réseau normal (pas de cache de données privées).
});
"""
    resp = HttpResponse(js, content_type="application/javascript")
    resp["Service-Worker-Allowed"] = "/"
    return resp


@login_required
def home(request):
    user = request.user

    # Les externes sont redirigés vers leur portail dédié.
    if user.is_external:
        return redirect("extranet:home")

    today = timezone.localdate()
    open_tasks = Task.objects.filter(assigned_to=user).exclude(
        status__in=[Task.Status.DONE, Task.Status.CANCELLED]
    )
    from notifications.models import Notification
    visible_news = News.objects.filter(
        is_published=True, mod_status=News.ModStatus.APPROVED)
    context = {
        "news": visible_news[:5],
        "pinned": visible_news.filter(is_pinned=True).first(),
        "events": Event.objects.filter(start__date__gte=today).order_by("start")[:5],
        "my_tasks": open_tasks[:6],
        # Compteurs des cartes statistiques
        "count_tasks": open_tasks.count(),
        "count_docs": Document.objects.filter(is_archived=False).count(),
        "count_news": visible_news.count(),
        "count_notifs": Notification.objects.filter(recipient=user, is_read=False).count(),
    }

    # Solde de congés personnel.
    employee = Employee.objects.filter(user=user).first()
    if employee:
        context["employee"] = employee
        context["leave_balance"] = solde_conges(employee)
        context["my_leaves"] = employee.leave_requests.all()[:4]

    # Statistiques globales (responsables, RH, CEO, admin).
    if user.is_manager:
        context["stats"] = {
            "employees": Employee.objects.filter(
                status__in=[Employee.Status.ACTIVE, Employee.Status.LEAVE]).count(),
            "documents": Document.objects.filter(is_archived=False).count(),
            "news": visible_news.count(),
            "pending_leaves": LeaveRequest.objects.filter(status=LeaveRequest.Status.PENDING).count(),
        }
        # Anniversaires imminents (≤ 3 jours) : RH/CEO/admin → tout le personnel ;
        # responsable → son équipe. La liste complète est dans l'espace RH.
        from employees.models import upcoming_birthdays
        emps = Employee.objects.filter(status=Employee.Status.ACTIVE).select_related("user")
        if not user.is_rh:
            emps = emps.filter(manager__user=user)
        context["birthdays"] = upcoming_birthdays(emps, within_days=3)

    # File de validation des congés : demandes où l'utilisateur peut décider maintenant.
    if user.can_validate_leave:
        from conges.views import _can_act
        pending = (LeaveRequest.objects.filter(status=LeaveRequest.Status.PENDING)
                   .select_related("employee__user", "employee__manager__user", "leave_type"))
        context["leave_queue"] = [lr for lr in pending if _can_act(user, lr)][:6]

    return render(request, "dashboard/home.html", context)
