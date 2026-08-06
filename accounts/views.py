from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count
from .models import UserProfile


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


def login_view(request):
    if request.user.is_authenticated:
        return redirect("core:dashboard")
    if request.method == "POST":
        username = request.POST.get("username", "")
        password = request.POST.get("password", "")
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect(request.GET.get("next", "core:dashboard"))
        else:
            messages.error(request, "Nom d'utilisateur ou mot de passe incorrect.")
    return render(request, "accounts/login.html")


@login_required
def logout_view(request):
    logout(request)
    return redirect("accounts:login")


@login_required
def profile_view(request, pk=None):
    """Own profile (pk=None) or admin viewing another user's profile."""
    if pk and pk != request.user.pk:
        if not request.user.profile.is_admin():
            messages.error(request, "Accès réservé aux administrateurs.")
            return redirect("core:dashboard")
        viewed_user = get_object_or_404(User, pk=pk)
    else:
        viewed_user = request.user

    return render(
        request,
        "accounts/profile.html",
        {
            "viewed_user": viewed_user,
            "is_own_profile": viewed_user.pk == request.user.pk,
        },
    )


@login_required
def password_change_view(request, pk=None):
    """Change own password, or admin changes another user's password."""
    if pk and pk != request.user.pk:
        if not request.user.profile.is_admin():
            messages.error(request, "Accès réservé aux administrateurs.")
            return redirect("core:dashboard")
        target_user = get_object_or_404(User, pk=pk)
        admin_mode = True
    else:
        target_user = request.user
        admin_mode = False

    if request.method == "POST":
        if not admin_mode:
            if not target_user.check_password(request.POST.get("current_password", "")):
                messages.error(request, "Mot de passe actuel incorrect.")
                return render(
                    request,
                    "accounts/password_change.html",
                    {
                        "target_user": target_user,
                        "admin_mode": admin_mode,
                    },
                )

        p1 = request.POST.get("password1", "")
        p2 = request.POST.get("password2", "")

        if not p1:
            messages.error(request, "Le nouveau mot de passe est requis.")
        elif p1 != p2:
            messages.error(request, "Les mots de passe ne correspondent pas.")
        elif len(p1) < 8:
            messages.error(
                request, "Le mot de passe doit contenir au moins 8 caractères."
            )
        else:
            target_user.set_password(p1)
            target_user.save()
            if not admin_mode:
                update_session_auth_hash(request, target_user)
            messages.success(
                request, f"Mot de passe de « {target_user.username} » modifié."
            )
            return (
                redirect("accounts:user_profile", pk=target_user.pk)
                if admin_mode
                else redirect("accounts:profile")
            )

    return render(
        request,
        "accounts/password_change.html",
        {
            "target_user": target_user,
            "admin_mode": admin_mode,
        },
    )


# ---------------------------------------------------------------------------
# User management — Admin only
# ---------------------------------------------------------------------------


USER_SORT = {"last_name", "profile__role", "last_login", "is_active"}


@login_required
def user_list(request):
    if not request.user.profile.is_admin():
        messages.error(request, "Accès réservé aux administrateurs.")
        return redirect("core:dashboard")
    sort = request.GET.get("sort", "last_name")
    dir = request.GET.get("dir", "asc")
    if sort not in USER_SORT:
        sort = "last_name"
    qs = User.objects.select_related("profile")
    qs = qs.order_by(sort if dir == "asc" else "-" + sort)
    page_obj = Paginator(qs, 20).get_page(request.GET.get("page"))
    return render(
        request,
        "accounts/user_list.html",
        {
            "page_obj": page_obj,
            "sort": sort,
            "dir": dir,
        },
    )


@login_required
def user_create(request):
    if not request.user.profile.is_admin():
        messages.error(request, "Accès réservé aux administrateurs.")
        return redirect("accounts:user_list")

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        p1, p2 = request.POST.get("password1", ""), request.POST.get("password2", "")
        errors = []
        if not username:
            errors.append("Le nom d'utilisateur est requis.")
        elif User.objects.filter(username=username).exists():
            errors.append("Ce nom d'utilisateur est déjà utilisé.")
        if not p1:
            errors.append("Le mot de passe est requis.")
        elif p1 != p2:
            errors.append("Les mots de passe ne correspondent pas.")
        elif len(p1) < 8:
            errors.append("Le mot de passe doit contenir au moins 8 caractères.")

        if errors:
            for e in errors:
                messages.error(request, e)
        else:
            user = User.objects.create_user(
                username=username,
                first_name=request.POST.get("first_name", "").strip(),
                last_name=request.POST.get("last_name", "").strip(),
                email=request.POST.get("email", "").strip(),
                password=p1,
            )
            user.profile.role = request.POST.get("role", "viewer")
            user.profile.phone = request.POST.get("phone", "").strip()
            user.profile.save()
            messages.success(request, f"Utilisateur « {user.username} » créé.")
            return redirect("accounts:user_list")

    return render(
        request,
        "accounts/user_form.html",
        {
            "title": "Nouvel utilisateur",
            "role_choices": UserProfile.ROLE_CHOICES,
        },
    )


@login_required
def user_edit(request, pk):
    if not request.user.profile.is_admin():
        messages.error(request, "Accès réservé aux administrateurs.")
        return redirect("accounts:user_list")

    target_user = get_object_or_404(User, pk=pk)

    if request.method == "POST":
        target_user.first_name = request.POST.get("first_name", "").strip()
        target_user.last_name = request.POST.get("last_name", "").strip()
        target_user.email = request.POST.get("email", "").strip()
        if target_user.pk != request.user.pk:
            target_user.is_active = request.POST.get("is_active") == "on"
        target_user.save()
        target_user.profile.role = request.POST.get("role", "viewer")
        target_user.profile.phone = request.POST.get("phone", "").strip()
        target_user.profile.save()
        messages.success(request, f"Utilisateur « {target_user.username} » modifié.")
        return redirect("accounts:user_profile", pk=target_user.pk)

    return render(
        request,
        "accounts/user_form.html",
        {
            "title": "Modifier utilisateur",
            "target_user": target_user,
            "role_choices": UserProfile.ROLE_CHOICES,
        },
    )


@login_required
def user_delete(request, pk):
    if not request.user.profile.is_admin():
        messages.error(request, "Accès réservé aux administrateurs.")
        return redirect("accounts:user_list")
    if pk == request.user.pk:
        messages.error(request, "Impossible de supprimer votre propre compte.")
        return redirect("accounts:user_list")
    target_user = get_object_or_404(User, pk=pk)
    if request.method == "POST":
        username = target_user.username
        target_user.delete()
        messages.success(request, f"Utilisateur « {username} » supprimé.")
    return redirect("accounts:user_list")
