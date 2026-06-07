"""Notifications : liste, marquage lu, redirection, diffusion (broadcast)."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from accounts.models import Role, User
from accounts.utils import log_activity, role_required

from .forms import BroadcastForm
from .models import Notification, notify


def _current_audience(user):
    """Périmètre actif du visiteur : extranet pour un externe, sinon intranet."""
    return (Notification.Audience.EXTERNAL if user.is_external
            else Notification.Audience.INTERNAL)


@login_required
def notification_list(request):
    notifs = Notification.objects.filter(
        recipient=request.user, audience=_current_audience(request.user)
    )
    return render(request, "notifications/list.html", {
        "notifs": notifs, "audience": _current_audience(request.user),
    })


@login_required
def open_notification(request, pk):
    notif = get_object_or_404(Notification, pk=pk, recipient=request.user)
    notif.is_read = True
    notif.save(update_fields=["is_read"])
    return redirect(notif.url or "notifications:list")


@login_required
def mark_all_read(request):
    Notification.objects.filter(
        recipient=request.user, audience=_current_audience(request.user), is_read=False
    ).update(is_read=True)
    return redirect("notifications:list")


@login_required
def delete_notification(request, pk):
    """Chacun peut supprimer une notification de sa propre liste."""
    notif = get_object_or_404(Notification, pk=pk, recipient=request.user)
    if request.method == "POST":
        notif.delete()
        messages.success(request, "Notification supprimée.")
    return redirect("notifications:list")


@login_required
def clear_notifications(request):
    """Vide la liste de notifications de l'utilisateur (périmètre actif)."""
    if request.method == "POST":
        Notification.objects.filter(
            recipient=request.user, audience=_current_audience(request.user)).delete()
        messages.success(request, "Notifications effacées.")
    return redirect("notifications:list")


@role_required(Role.RH, Role.CEO, Role.ADMIN)
def broadcast(request):
    """LPM diffuse une annonce au personnel (intranet) et/ou aux clients (extranet).

    Le périmètre (intranet/extranet) de chaque notification est déduit
    automatiquement du destinataire par notify().
    """
    if request.method == "POST":
        form = BroadcastForm(request.POST, viewer=request.user)
        if form.is_valid():
            roles = form.recipient_roles()
            recipients = (User.objects.filter(role__in=roles, is_active=True)
                          .exclude(pk=request.user.pk))
            url = (form.cleaned_data.get("url") or "").strip()
            sent = 0
            for u in recipients:
                notify(u, form.cleaned_data["title"], form.cleaned_data["message"],
                       form.cleaned_data["level"], url)
                sent += 1
            log_activity(request, "CREATE",
                         f"Diffusion notification « {form.cleaned_data['title']} » à {sent} destinataire(s)")
            messages.success(request, f"Annonce diffusée à {sent} destinataire(s).")
            return redirect("notifications:broadcast")
    else:
        form = BroadcastForm(viewer=request.user)
    return render(request, "notifications/broadcast.html", {"form": form})
