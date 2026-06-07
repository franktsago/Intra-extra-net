"""Vues Marketing : campagnes, calendrier éditorial, médiathèque."""

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.models import Role
from accounts.utils import internal_required, role_required
from notifications.models import Notification, notify
from django.urls import reverse

from .forms import CampaignForm, MediaAssetForm, PostForm
from .models import Campaign, MediaAsset, Post

manager_required = role_required(Role.ADMIN, Role.CEO, Role.RH, Role.MANAGER)


# --------------------------------------------------------------------------- #
# Campagnes
# --------------------------------------------------------------------------- #
@internal_required
def campaign_list(request):
    channel = request.GET.get("channel", "")
    qs = Campaign.objects.select_related("brand", "manager")
    if channel:
        qs = qs.filter(channel=channel)
    return render(request, "marketing/campaign_list.html", {
        "campaigns": qs, "channel": channel, "channels": Campaign.Channel.choices})


@internal_required
def campaign_detail(request, pk):
    campaign = get_object_or_404(
        Campaign.objects.select_related("brand", "manager", "project").prefetch_related("posts"), pk=pk)
    return render(request, "marketing/campaign_detail.html", {
        "campaign": campaign, "can_edit": request.user.is_manager})


@manager_required
def campaign_edit(request, pk=None):
    obj = get_object_or_404(Campaign, pk=pk) if pk else None
    if request.method == "POST":
        form = CampaignForm(request.POST, instance=obj, viewer=request.user)
        if form.is_valid():
            c = form.save(commit=False)
            if not obj and not c.manager:
                c.manager = request.user
            c.save()
            messages.success(request, "Campagne enregistrée.")
            return redirect("marketing:campaign_detail", pk=c.pk)
    else:
        form = CampaignForm(instance=obj, viewer=request.user)
    return render(request, "marketing/campaign_form.html", {"form": form, "obj": obj})


# --------------------------------------------------------------------------- #
# Calendrier éditorial
# --------------------------------------------------------------------------- #
@internal_required
def calendar(request):
    status = request.GET.get("status", "")
    posts = Post.objects.select_related("brand", "campaign", "author")
    if status:
        posts = posts.filter(status=status)
    today = timezone.now()
    return render(request, "marketing/calendar.html", {
        "upcoming": posts.filter(scheduled_at__gte=today),
        "past": posts.filter(scheduled_at__lt=today).order_by("-scheduled_at")[:20],
        "status": status, "statuses": Post.Status.choices,
        "pending_count": Post.objects.filter(status=Post.Status.PENDING).count(),
    })


@internal_required
def post_edit(request, pk=None):
    post = get_object_or_404(Post, pk=pk) if pk else None
    if request.method == "POST":
        form = PostForm(request.POST, request.FILES, instance=post)
        if form.is_valid():
            p = form.save(commit=False)
            if not post:
                p.author = request.user
            p.save()
            messages.success(request, "Publication enregistrée.")
            return redirect("marketing:calendar")
    else:
        form = PostForm(instance=post)
    return render(request, "marketing/post_form.html", {"form": form, "post": post})


@internal_required
def post_status(request, pk, action):
    post = get_object_or_404(Post, pk=pk)
    user = request.user
    if action == "submit" and post.author_id == user.id:
        post.status = Post.Status.PENDING
        post.save(update_fields=["status"])
        # Notifier les responsables marketing.
        from accounts.models import User
        for m in User.objects.filter(role__in=[Role.MANAGER, Role.CEO, Role.ADMIN], is_active=True):
            notify(m, "Contenu à valider", f"« {post.title} » attend votre validation.",
                   Notification.Level.INFO, reverse("marketing:calendar"))
        messages.success(request, "Publication soumise à validation.")
    elif action in {"approve", "reject", "publish"} and user.is_manager:
        if action == "approve":
            post.status = Post.Status.APPROVED
        elif action == "reject":
            post.status = Post.Status.REJECTED
        else:
            post.status = Post.Status.PUBLISHED
        post.validator = user
        post.save(update_fields=["status", "validator"])
        notify(post.author, f"Contenu {post.get_status_display().lower()}",
               f"« {post.title} »", Notification.Level.INFO, reverse("marketing:calendar"))
        messages.success(request, "Statut de la publication mis à jour.")
    return redirect("marketing:calendar")


# --------------------------------------------------------------------------- #
# Médiathèque
# --------------------------------------------------------------------------- #
@internal_required
def library(request):
    kind = request.GET.get("kind", "")
    brand = request.GET.get("brand", "")
    assets = MediaAsset.objects.select_related("brand")
    if kind:
        assets = assets.filter(kind=kind)
    if brand:
        assets = assets.filter(brand_id=brand)
    from business.models import Client
    return render(request, "marketing/library.html", {
        "assets": assets, "kind": kind, "brand": brand,
        "kinds": MediaAsset.Kind.choices,
        "brands": Client.objects.all(),
        "form": MediaAssetForm(),
    })


@internal_required
def media_upload(request):
    if request.method == "POST":
        form = MediaAssetForm(request.POST, request.FILES)
        if form.is_valid():
            a = form.save(commit=False)
            a.uploaded_by = request.user
            a.save()
            messages.success(request, "Média ajouté à la bibliothèque.")
    return redirect("marketing:library")
