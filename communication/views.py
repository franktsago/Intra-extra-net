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


@internal_required
def news_list(request):
    q = request.GET.get("q", "").strip()
    news = News.objects.filter(is_published=True).select_related("author")
    if q:
        news = news.filter(Q(title__icontains=q) | Q(content__icontains=q))
    page = Paginator(news, 8).get_page(request.GET.get("page"))
    return render(request, "communication/news_list.html", {"page_obj": page, "q": q})


@internal_required
def news_detail(request, slug):
    article = get_object_or_404(News, slug=slug, is_published=True)
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
        "comments": article.comments.select_related("author"),
    })


# Gestion des actualités : réservée à RH / CEO / Administrateur principal.
# Les autres rôles internes (employé, stagiaire, responsable) consultent uniquement.
@role_required(Role.ADMIN, Role.CEO, Role.RH)
def news_edit(request, pk=None):
    article = get_object_or_404(News, pk=pk) if pk else None
    if request.method == "POST":
        form = NewsForm(request.POST, request.FILES, instance=article)
        if form.is_valid():
            obj = form.save(commit=False)
            if not article:
                obj.author = request.user
            obj.save()
            messages.success(request, "Actualité enregistrée.")
            return redirect("communication:detail", slug=obj.slug)
    else:
        form = NewsForm(instance=article)
    return render(request, "communication/news_form.html", {"form": form, "article": article})


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
