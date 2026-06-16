"""Actualités, commentaires et calendrier des événements."""

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.models import Role
from accounts.utils import internal_required, role_required

from .forms import CommentForm, EventForm, NewsForm
from .models import Event, News

manager_required = role_required(Role.ADMIN, Role.CEO, Role.RH, Role.MANAGER)


def _can_moderate_news(user):
    """RH, CEO et administrateur principal valident/refusent les actualités."""
    return user.is_rh  # is_rh inclut CEO et admin


@internal_required
def news_list(request):
    q = request.GET.get("q", "").strip()
    news = News.objects.filter(
        is_published=True, mod_status=News.ModStatus.APPROVED
    ).select_related("author")
    if q:
        news = news.filter(Q(title__icontains=q) | Q(content__icontains=q))
    page = Paginator(news, 8).get_page(request.GET.get("page"))
    # Compteur d'actualités en attente (pour les valideurs).
    pending_count = (News.objects.filter(mod_status=News.ModStatus.PENDING).count()
                     if _can_moderate_news(request.user) else 0)
    return render(request, "communication/news_list.html", {
        "page_obj": page, "q": q, "pending_count": pending_count,
        "can_moderate": _can_moderate_news(request.user),
    })


@internal_required
def news_detail(request, slug):
    article = get_object_or_404(News, slug=slug)
    # Une actualité non encore validée n'est visible que par son auteur et les valideurs.
    if not article.is_visible:
        if not (_can_moderate_news(request.user) or article.author_id == request.user.id):
            from django.http import Http404
            raise Http404("Actualité introuvable.")
    if request.method == "POST":
        form = CommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.news = article
            comment.author = request.user
            comment.save()
            messages.success(request, "Commentaire publié.")
            return redirect("communication:detail", slug=slug)
    else:
        form = CommentForm()
    return render(request, "communication/news_detail.html", {
        "article": article, "form": form,
        "can_moderate": _can_moderate_news(request.user),
        "comments": article.comments.select_related("author"),
    })


# Création/édition d'actualités : ouverte aux responsables ET à la RH/CEO/admin.
# Une actualité créée par un responsable passe en validation avant publication.
@role_required(Role.ADMIN, Role.CEO, Role.RH, Role.MANAGER)
def news_edit(request, pk=None):
    article = get_object_or_404(News, pk=pk) if pk else None
    if request.method == "POST":
        form = NewsForm(request.POST, request.FILES, instance=article)
        if form.is_valid():
            obj = form.save(commit=False)
            if not article:
                obj.author = request.user
            # La RH/CEO/admin publie directement ; un responsable passe en attente.
            if _can_moderate_news(request.user):
                obj.mod_status = News.ModStatus.APPROVED
                if not obj.reviewed_at:
                    obj.reviewed_by = request.user
                    obj.reviewed_at = timezone.now()
            elif not article:
                # Nouvelle actualité d'un responsable → file de validation.
                obj.mod_status = News.ModStatus.PENDING
            obj.save()
            if obj.mod_status == News.ModStatus.PENDING:
                _notify_moderators(obj)
                messages.success(
                    request,
                    "Actualité soumise. Elle sera publiée après validation par la RH / la Direction.",
                )
            else:
                messages.success(request, "Actualité enregistrée.")
            return redirect("communication:detail", slug=obj.slug)
    else:
        form = NewsForm(instance=article)
    return render(request, "communication/news_form.html", {"form": form, "article": article})


def _notify_moderators(article):
    """Prévient les valideurs (RH/CEO/admin) qu'une actualité attend validation."""
    from django.urls import reverse
    from accounts.models import Role, User
    from notifications.models import notify
    author = article.author.get_full_name() if article.author else "Un responsable"
    url = reverse("communication:moderation")
    for u in User.objects.filter(role__in=[Role.RH, Role.CEO, Role.ADMIN], is_active=True):
        notify(u, "Actualité à valider",
               f"{author} a soumis l'actualité « {article.title} ».", url=url)


@role_required(Role.ADMIN, Role.CEO, Role.RH)
def news_moderation(request):
    """File des actualités en attente de validation."""
    pending = News.objects.filter(
        mod_status=News.ModStatus.PENDING).select_related("author").order_by("created_at")
    return render(request, "communication/news_moderation.html", {"pending": pending})


@role_required(Role.ADMIN, Role.CEO, Role.RH)
def news_approve(request, pk):
    article = get_object_or_404(News, pk=pk)
    if request.method == "POST":
        article.mod_status = News.ModStatus.APPROVED
        article.is_published = True
        article.reviewed_by = request.user
        article.reviewed_at = timezone.now()
        article.reject_reason = ""
        article.save()
        if article.author_id:
            from django.urls import reverse
            from notifications.models import notify
            notify(article.author, "Actualité validée",
                   f"Votre actualité « {article.title} » a été publiée.",
                   url=reverse("communication:detail", args=[article.slug]))
        messages.success(request, f"Actualité « {article.title} » validée et publiée.")
    return redirect("communication:moderation")


@role_required(Role.ADMIN, Role.CEO, Role.RH)
def news_reject(request, pk):
    article = get_object_or_404(News, pk=pk)
    if request.method == "POST":
        article.mod_status = News.ModStatus.REJECTED
        article.is_published = False
        article.reviewed_by = request.user
        article.reviewed_at = timezone.now()
        article.reject_reason = (request.POST.get("reason") or "").strip()
        article.save()
        if article.author_id:
            from notifications.models import notify
            motif = f" Motif : {article.reject_reason}" if article.reject_reason else ""
            notify(article.author, "Actualité refusée",
                   f"Votre actualité « {article.title} » n'a pas été retenue.{motif}")
        messages.success(request, f"Actualité « {article.title} » refusée.")
    return redirect("communication:moderation")


@role_required(Role.ADMIN, Role.CEO, Role.RH)
def news_delete(request, pk):
    article = get_object_or_404(News, pk=pk)
    if request.method == "POST":
        title = article.title
        article.delete()
        messages.success(request, f"Actualité « {title} » supprimée.")
        return redirect("communication:list")
    return render(request, "communication/news_confirm_delete.html", {"article": article})


@internal_required
def calendar(request):
    today = timezone.localdate()
    upcoming = Event.objects.filter(start__date__gte=today).order_by("start")
    past = Event.objects.filter(start__date__lt=today).order_by("-start")[:10]
    return render(request, "communication/calendar.html", {"upcoming": upcoming, "past": past})


@role_required(Role.ADMIN, Role.CEO, Role.RH, Role.MANAGER)
def event_create(request):
    if request.method == "POST":
        form = EventForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.created_by = request.user
            obj.save()
            messages.success(request, "Événement ajouté au calendrier.")
            return redirect("communication:calendar")
    else:
        form = EventForm()
    return render(request, "communication/event_form.html", {"form": form})


# --------------------------------------------------------------------------- #
# Revue de presse
# --------------------------------------------------------------------------- #
@internal_required
def press_list(request):
    from .models import PressReview
    tone = request.GET.get("tone", "")
    qs = PressReview.objects.select_related("added_by")
    if tone:
        qs = qs.filter(tone=tone)
    return render(request, "communication/press_list.html", {
        "reviews": qs, "tone": tone, "tones": PressReview.Tone.choices,
    })


@manager_required
def press_edit(request, pk=None):
    from .models import PressReview
    from .forms import PressReviewForm
    obj = get_object_or_404(PressReview, pk=pk) if pk else None
    if request.method == "POST":
        form = PressReviewForm(request.POST, instance=obj)
        if form.is_valid():
            p = form.save(commit=False)
            if not obj:
                p.added_by = request.user
            p.save()
            messages.success(request, "Article enregistré.")
            return redirect("communication:press_list")
    else:
        form = PressReviewForm(instance=obj)
    return render(request, "communication/press_form.html", {"form": form, "obj": obj})


# --------------------------------------------------------------------------- #
# Messages clés
# --------------------------------------------------------------------------- #
@internal_required
def key_messages(request):
    from .models import KeyMessage
    qs = KeyMessage.objects.filter(is_active=True)
    by_cat = {}
    for km in qs:
        by_cat.setdefault(km.get_category_display(), []).append(km)
    return render(request, "communication/key_messages.html", {"by_cat": by_cat})


@manager_required
def key_message_edit(request, pk=None):
    from .models import KeyMessage
    from .forms import KeyMessageForm
    obj = get_object_or_404(KeyMessage, pk=pk) if pk else None
    if request.method == "POST":
        form = KeyMessageForm(request.POST, instance=obj)
        if form.is_valid():
            km = form.save(commit=False)
            if not obj:
                km.created_by = request.user
            km.save()
            messages.success(request, "Message clé enregistré.")
            return redirect("communication:key_messages")
    else:
        form = KeyMessageForm(instance=obj)
    return render(request, "communication/key_message_form.html", {"form": form, "obj": obj})


# --------------------------------------------------------------------------- #
# Newsletters
# --------------------------------------------------------------------------- #
@internal_required
def newsletter_list(request):
    from .models import Newsletter
    qs = Newsletter.objects.select_related("created_by")
    return render(request, "communication/newsletter_list.html", {"newsletters": qs})


@manager_required
def newsletter_edit(request, pk=None):
    from .models import Newsletter
    from .forms import NewsletterForm
    obj = get_object_or_404(Newsletter, pk=pk) if pk else None
    if request.method == "POST":
        form = NewsletterForm(request.POST, instance=obj)
        if form.is_valid():
            n = form.save(commit=False)
            if not obj:
                n.created_by = request.user
            n.save()
            messages.success(request, "Newsletter enregistrée.")
            return redirect("communication:newsletter_list")
    else:
        form = NewsletterForm(instance=obj)
    return render(request, "communication/newsletter_form.html", {"form": form, "obj": obj})


# --------------------------------------------------------------------------- #
# Événementiel
# --------------------------------------------------------------------------- #
@internal_required
def event_projects(request):
    from .models import EventProject
    qs = EventProject.objects.select_related("responsible")
    return render(request, "communication/event_projects.html", {"event_projects": qs})


@internal_required
def event_project_detail(request, pk):
    from .models import EventProject
    ep = get_object_or_404(EventProject.objects.prefetch_related("suppliers", "participants"), pk=pk)
    report = getattr(ep, "report", None)
    return render(request, "communication/event_project_detail.html", {
        "ep": ep, "report": report})


@manager_required
def event_project_edit(request, pk=None):
    from .models import EventProject
    from .forms import EventProjectForm
    obj = get_object_or_404(EventProject, pk=pk) if pk else None
    if request.method == "POST":
        form = EventProjectForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Projet événement enregistré.")
            return redirect("communication:event_projects")
    else:
        form = EventProjectForm(instance=obj)
    return render(request, "communication/event_project_form.html", {"form": form, "obj": obj})


@manager_required
def event_participant_add(request, pk):
    from .models import EventProject
    from .forms import EventParticipantForm
    ep = get_object_or_404(EventProject, pk=pk)
    if request.method == "POST":
        form = EventParticipantForm(request.POST)
        if form.is_valid():
            p = form.save(commit=False)
            p.event_project = ep
            p.save()
            messages.success(request, "Participant ajouté.")
    return redirect("communication:event_project_detail", pk=pk)


@manager_required
def event_report_edit(request, pk):
    from .models import EventProject, EventReport
    from .forms import EventReportForm
    ep = get_object_or_404(EventProject, pk=pk)
    report = getattr(ep, "report", None)
    if request.method == "POST":
        form = EventReportForm(request.POST, instance=report)
        if form.is_valid():
            r = form.save(commit=False)
            r.event_project = ep
            if not report:
                r.created_by = request.user
            r.save()
            messages.success(request, "Bilan enregistré.")
    return redirect("communication:event_project_detail", pk=pk)
