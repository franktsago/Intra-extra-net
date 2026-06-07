"""Compteurs « relation client » exposés à l'intranet (réclamations, demandes)."""

from .models import ClientRequest, Ticket


def client_inbox_badges(request):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated or not getattr(user, "is_manager", False):
        return {"open_tickets_count": 0, "pending_requests": 0}
    return {
        "open_tickets_count": Ticket.objects.filter(
            status__in=[Ticket.Status.OPEN, Ticket.Status.IN_PROGRESS]).count(),
        "pending_requests": ClientRequest.objects.filter(
            status=ClientRequest.Status.SUBMITTED).count(),
    }
