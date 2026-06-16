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
@manager_required
def campaign_list(request):
    channel = request.GET.get("channel", "")
    qs = Campaign.objects.select_related("brand", "manager")
    if channel:
        qs = qs.filter(channel=channel)
    return render(request, "marketing/campaign_list.html", {
        "campaigns": qs, "channel": channel, "channels": Campaign.Channel.choices})


@manager_required
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
@manager_required
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


@manager_required
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


@manager_required
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
@manager_required
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


@manager_required
def media_upload(request):
    if request.method == "POST":
        form = MediaAssetForm(request.POST, request.FILES)
        if form.is_valid():
            a = form.save(commit=False)
            a.uploaded_by = request.user
            a.save()
            messages.success(request, "Média ajouté à la bibliothèque.")
    return redirect("marketing:library")


# --------------------------------------------------------------------------- #
# KPI Dashboard
# --------------------------------------------------------------------------- #
@manager_required
def kpi_dashboard(request):
    from collections import Counter
    from .models import Lead, AdCampaign, EmailCampaign, ABTest
    campaigns = Campaign.objects.all()
    total_reach = sum((c.actual_reach or 0) for c in campaigns)
    total_leads_db = Lead.objects.count()
    total_budget = sum(float(c.budget) for c in campaigns)
    active_campaigns = campaigns.filter(status=Campaign.Status.ACTIVE).count()
    leads_by_source = Counter(Lead.objects.values_list("source", flat=True))
    leads_by_status = Counter(Lead.objects.values_list("status", flat=True))
    return render(request, "marketing/kpi_dashboard.html", {
        "total_reach": total_reach, "total_leads_db": total_leads_db,
        "total_budget": int(total_budget), "active_campaigns": active_campaigns,
        "campaigns": campaigns[:6],
        "leads_by_source": dict(leads_by_source),
        "leads_by_status": dict(leads_by_status),
    })


# --------------------------------------------------------------------------- #
# Leads / Prospects
# --------------------------------------------------------------------------- #
@manager_required
def lead_list(request):
    from .models import Lead
    status = request.GET.get("status", "")
    source = request.GET.get("source", "")
    qs = Lead.objects.select_related("campaign", "assigned_to")
    if status:
        qs = qs.filter(status=status)
    if source:
        qs = qs.filter(source=source)
    return render(request, "marketing/lead_list.html", {
        "leads": qs, "status": status, "source": source,
        "statuses": Lead.Status.choices, "sources": Lead.Source.choices,
    })


@manager_required
def lead_edit(request, pk=None):
    from .models import Lead
    from .forms import LeadForm
    obj = get_object_or_404(Lead, pk=pk) if pk else None
    if request.method == "POST":
        form = LeadForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Lead enregistré.")
            return redirect("marketing:lead_list")
    else:
        form = LeadForm(instance=obj)
    return render(request, "marketing/lead_form.html", {"form": form, "obj": obj})


# --------------------------------------------------------------------------- #
# Marketing Digital
# --------------------------------------------------------------------------- #
@manager_required
def digital_hub(request):
    from .models import SEOKeyword, AdCampaign, EmailCampaign, ABTest
    seo_top = SEOKeyword.objects.order_by("position")[:5]
    ads = AdCampaign.objects.filter(status=AdCampaign.Status.ACTIVE)[:4]
    emails = EmailCampaign.objects.order_by("-created_at")[:4]
    abtests = ABTest.objects.order_by("-created_at")[:4]
    return render(request, "marketing/digital_hub.html", {
        "seo_top": seo_top, "ads": ads, "emails": emails, "abtests": abtests,
    })


@manager_required
def seo_list(request):
    from .models import SEOKeyword
    qs = SEOKeyword.objects.all()
    return render(request, "marketing/seo_list.html", {"keywords": qs})


@manager_required
def seo_edit(request, pk=None):
    from .models import SEOKeyword
    from .forms import SEOKeywordForm
    obj = get_object_or_404(SEOKeyword, pk=pk) if pk else None
    if request.method == "POST":
        form = SEOKeywordForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Mot-clé SEO enregistré.")
            return redirect("marketing:seo_list")
    else:
        form = SEOKeywordForm(instance=obj)
    return render(request, "marketing/seo_form.html", {"form": form, "obj": obj})


@manager_required
def ads_list(request):
    from .models import AdCampaign
    qs = AdCampaign.objects.order_by("-created_at")
    return render(request, "marketing/ads_list.html", {"ads": qs})


@manager_required
def ads_edit(request, pk=None):
    from .models import AdCampaign
    from .forms import AdCampaignForm
    obj = get_object_or_404(AdCampaign, pk=pk) if pk else None
    if request.method == "POST":
        form = AdCampaignForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Campagne Ads enregistrée.")
            return redirect("marketing:ads_list")
    else:
        form = AdCampaignForm(instance=obj)
    return render(request, "marketing/ads_form.html", {"form": form, "obj": obj})


@manager_required
def email_list(request):
    from .models import EmailCampaign
    qs = EmailCampaign.objects.order_by("-created_at")
    return render(request, "marketing/email_list.html", {"emails": qs})


@manager_required
def email_edit(request, pk=None):
    from .models import EmailCampaign
    from .forms import EmailCampaignForm
    obj = get_object_or_404(EmailCampaign, pk=pk) if pk else None
    if request.method == "POST":
        form = EmailCampaignForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Email enregistré.")
            return redirect("marketing:email_list")
    else:
        form = EmailCampaignForm(instance=obj)
    return render(request, "marketing/email_form.html", {"form": form, "obj": obj})


@manager_required
def abtest_list(request):
    from .models import ABTest
    qs = ABTest.objects.order_by("-created_at")
    return render(request, "marketing/abtest_list.html", {"abtests": qs})


@manager_required
def abtest_edit(request, pk=None):
    from .models import ABTest
    from .forms import ABTestForm
    obj = get_object_or_404(ABTest, pk=pk) if pk else None
    if request.method == "POST":
        form = ABTestForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Test A/B enregistré.")
            return redirect("marketing:abtest_list")
    else:
        form = ABTestForm(instance=obj)
    return render(request, "marketing/abtest_form.html", {"form": form, "obj": obj})
