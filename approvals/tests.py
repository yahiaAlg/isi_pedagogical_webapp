from datetime import timedelta

from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from formations.models import Category, Formation

from . import services
from .models import ApprovalRequest as R
from .models import Notification


def make_user(username, role, email=True):
    u = User.objects.create_user(
        username, email=f"{username}@isi.test" if email else "", password="pw-12345678"
    )
    u.profile.role = role
    u.profile.save()
    return u


FORMATION_POST = {
    "title": "Travail en hauteur",
    "code": "HAUT1",
    "duration_days": 2,
    "duration_hours": 14,
    "min_participants": 6,
    "max_participants": 12,
    "evaluation_type": "",  # filled in setUp from the model choices
    "passing_score": "10",
    "max_score": "20",
    "min_attendance_days": 1,
    "produces_certificate": "on",
    "is_active": "on",
}


@override_settings(APPROVAL_MAIL_ASYNC=False, EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class ApprovalFlowTests(TestCase):
    def setUp(self):
        self.admin = make_user("admin1", "admin")
        self.admin2 = make_user("admin2", "admin")
        self.agent = make_user("agent", "pedagogical")
        self.staff = make_user("staff", "staff")
        self.formation = Formation.objects.create(
            title="Secourisme", code="SEC1", duration_days=1, duration_hours=7,
            min_participants=4, max_participants=10,
        )
        self.post = dict(FORMATION_POST, evaluation_type=Formation.EVALUATION_CHOICES[0][0])

    def run_on_commit(self):
        return self.captureOnCommitCallbacks(execute=True)

    # ── permissions ────────────────────────────────────────────────────────
    def test_agent_cannot_create_formation_directly(self):
        self.client.force_login(self.agent)
        r = self.client.get(reverse("formations:formation_create"))
        self.assertRedirects(r, reverse("approvals:request_formation_create"))
        r = self.client.post(reverse("formations:formation_create"), self.post)
        self.assertRedirects(r, reverse("approvals:request_formation_create"))
        self.assertFalse(Formation.objects.filter(title="Travail en hauteur").exists())

    def test_agent_keeps_other_admin_powers_but_not_users_or_delete(self):
        self.client.force_login(self.agent)
        self.assertEqual(self.client.get(reverse("formations:category_create")).status_code, 200)
        self.assertRedirects(
            self.client.get(reverse("accounts:user_list")), reverse("core:dashboard")
        )
        self.client.post(reverse("formations:formation_delete", args=[self.formation.pk]))
        self.assertTrue(Formation.objects.filter(pk=self.formation.pk).exists())
        p = self.agent.profile
        self.assertTrue(p.can_archive_sessions() and p.can_manage_sessions())

    def test_staff_is_unchanged(self):
        self.client.force_login(self.staff)
        r = self.client.get(reverse("formations:category_create"))
        self.assertEqual(r.status_code, 302)  # still admin-level only
        self.assertRedirects(
            self.client.get(reverse("formations:formation_edit", args=[self.formation.pk])),
            reverse("formations:formation_detail", args=[self.formation.pk]),
        )

    def test_only_admin_can_decide(self):
        req = R.objects.create(requester=self.agent, kind=R.KIND_EDIT, formation=self.formation)
        self.client.force_login(self.agent)
        self.client.post(reverse("approvals:request_approve", args=[req.pk]))
        req.refresh_from_db()
        self.assertEqual(req.status, R.STATUS_PENDING)

    # ── create flow ────────────────────────────────────────────────────────
    def test_create_request_notifies_all_admins_bell_and_mail(self):
        self.client.force_login(self.agent)
        with self.run_on_commit():
            r = self.client.post(
                reverse("approvals:request_formation_create"),
                {"title": "Soudage", "code": "SOU1", "message": "Demande client"},
            )
        req = R.objects.get()
        self.assertRedirects(r, reverse("approvals:request_detail", args=[req.pk]))
        self.assertEqual(
            set(Notification.objects.values_list("recipient__username", flat=True)),
            {"admin1", "admin2"},
        )
        self.assertEqual({m.to[0] for m in mail.outbox}, {"admin1@isi.test", "admin2@isi.test"})
        self.assertIn("Soudage", mail.outbox[0].body)
        self.assertIn("/approvals/requests/%d/" % req.pk, mail.outbox[0].body)

    def test_create_request_validation(self):
        with self.assertRaises(services.ApprovalError):
            services.submit_request(self.agent, R.KIND_CREATE, proposed_title="  ")
        with self.assertRaises(services.ApprovalError):
            services.submit_request(
                self.agent, R.KIND_CREATE, proposed_title="X", proposed_code="sec1"
            )

    def test_admin_creates_in_place_of_agent_and_agent_is_notified(self):
        req = services.submit_request(self.agent, R.KIND_CREATE, proposed_title="Travail en hauteur")
        self.client.force_login(self.admin)
        page = self.client.get(reverse("formations:formation_create") + f"?request={req.pk}")
        self.assertContains(page, "Travail en hauteur")
        mail.outbox.clear()
        with self.run_on_commit():
            r = self.client.post(
                reverse("formations:formation_create"), dict(self.post, request=req.pk)
            )
        formation = Formation.objects.get(title="Travail en hauteur")
        self.assertRedirects(r, reverse("formations:formation_detail", args=[formation.pk]))
        req.refresh_from_db()
        self.assertEqual(req.status, R.STATUS_FULFILLED)
        self.assertEqual(req.created_formation, formation)
        n = Notification.objects.get(recipient=self.agent)
        self.assertEqual(n.kind, Notification.KIND_FULFILLED)
        self.assertEqual([m.to[0] for m in mail.outbox], ["agent@isi.test"])
        # the other admins' "new request" bell entries are cleared
        self.assertFalse(
            Notification.objects.filter(kind=Notification.KIND_NEW_REQUEST, is_read=False).exists()
        )

    # ── edit flow ──────────────────────────────────────────────────────────
    def test_edit_blocked_without_approval(self):
        self.client.force_login(self.agent)
        url = reverse("formations:formation_edit", args=[self.formation.pk])
        self.assertRedirects(self.client.get(url), reverse("formations:formation_detail", args=[self.formation.pk]))
        self.client.post(url, dict(self.post, title="Hack"))
        self.formation.refresh_from_db()
        self.assertEqual(self.formation.title, "Secourisme")

    def test_edit_full_cycle(self):
        self.client.force_login(self.agent)
        with self.run_on_commit():
            self.client.post(
                reverse("approvals:request_formation_edit", args=[self.formation.pk]),
                {"message": "Corriger la durée"},
            )
        req = R.objects.get()
        self.assertEqual(req.status, R.STATUS_PENDING)
        self.assertEqual(Notification.objects.filter(kind="new_request").count(), 2)

        # duplicate request refused
        with self.assertRaises(services.ApprovalError):
            services.submit_request(self.agent, R.KIND_EDIT, formation=self.formation)

        # admin approves
        mail.outbox.clear()
        self.client.force_login(self.admin)
        with self.run_on_commit():
            self.client.post(reverse("approvals:request_approve", args=[req.pk]), {"note": "OK"})
        req.refresh_from_db()
        self.assertEqual(req.status, R.STATUS_APPROVED)
        self.assertEqual([m.to[0] for m in mail.outbox], ["agent@isi.test"])
        n = Notification.objects.get(recipient=self.agent, kind="approved")
        self.assertIn("/formations/formations/%d/edit/" % self.formation.pk, n.url)
        # second admin cannot re-decide
        with self.assertRaises(services.ApprovalError):
            services.approve_edit(req, self.admin2)

        # agent can now open + save the form, once
        self.client.force_login(self.agent)
        edit = reverse("formations:formation_edit", args=[self.formation.pk])
        self.assertEqual(self.client.get(edit).status_code, 200)
        mail.outbox.clear()
        with self.run_on_commit():
            r = self.client.post(edit, dict(self.post, title="Secourisme (maj)", code="SEC1"))
        self.assertRedirects(r, reverse("formations:formation_detail", args=[self.formation.pk]))
        self.formation.refresh_from_db()
        self.assertEqual(self.formation.title, "Secourisme (maj)")
        req.refresh_from_db()
        self.assertEqual(req.status, R.STATUS_FULFILLED)
        self.assertEqual({m.to[0] for m in mail.outbox}, {"admin1@isi.test", "admin2@isi.test"})
        self.assertEqual(Notification.objects.filter(kind="edit_done").count(), 2)
        # grant consumed
        self.assertEqual(self.client.get(edit).status_code, 302)

    def test_rejection_notifies_agent_and_keeps_form_closed(self):
        req = services.submit_request(self.agent, R.KIND_EDIT, formation=self.formation)
        self.client.force_login(self.admin)
        with self.run_on_commit():
            self.client.post(reverse("approvals:request_reject", args=[req.pk]), {"note": "Non"})
        req.refresh_from_db()
        self.assertEqual(req.status, R.STATUS_REJECTED)
        self.assertIn("Non", mail.outbox[-1].body)
        self.assertTrue(Notification.objects.filter(recipient=self.agent, kind="rejected").exists())
        self.client.force_login(self.agent)
        self.assertEqual(
            self.client.get(reverse("formations:formation_edit", args=[self.formation.pk])).status_code, 302
        )

    @override_settings(APPROVAL_GRANT_HOURS=24)
    def test_grant_expires(self):
        req = services.submit_request(self.agent, R.KIND_EDIT, formation=self.formation)
        services.approve_edit(req, self.admin)
        R.objects.filter(pk=req.pk).update(reviewed_at=timezone.now() - timedelta(hours=25))
        self.client.force_login(self.agent)
        self.assertEqual(
            self.client.get(reverse("formations:formation_edit", args=[self.formation.pk])).status_code, 302
        )
        # an expired grant doesn't block a fresh request
        services.submit_request(self.agent, R.KIND_EDIT, formation=self.formation)

    def test_cancel(self):
        req = services.submit_request(self.agent, R.KIND_CREATE, proposed_title="Test")
        with self.assertRaises(services.ApprovalError):
            services.cancel(req, self.admin)
        services.cancel(req, self.agent)
        req.refresh_from_db()
        self.assertEqual(req.status, R.STATUS_CANCELLED)
        self.assertTrue(Notification.objects.filter(kind="cancelled", recipient=self.admin).exists())

    def test_users_without_email_still_get_bell(self):
        nomail = make_user("admin3", "admin", email=False)
        with self.run_on_commit():
            services.submit_request(self.agent, R.KIND_CREATE, proposed_title="Z")
        self.assertTrue(Notification.objects.filter(recipient=nomail).exists())
        self.assertNotIn("", [m.to[0] for m in mail.outbox])

    @override_settings(EMAIL_BACKEND="approvals.tests.BrokenBackend")
    def test_smtp_failure_never_breaks_request(self):
        with self.run_on_commit():
            req = services.submit_request(self.agent, R.KIND_CREATE, proposed_title="Z")
        self.assertTrue(R.objects.filter(pk=req.pk).exists())
        self.assertEqual(Notification.objects.count(), 2)

    # ── bell ───────────────────────────────────────────────────────────────
    def test_bell_feed_open_and_read_all(self):
        services.submit_request(self.agent, R.KIND_CREATE, proposed_title="A")
        services.submit_request(self.agent, R.KIND_CREATE, proposed_title="B")
        self.client.force_login(self.admin)
        data = self.client.get(reverse("approvals:notification_feed")).json()
        self.assertEqual(data["count"], 2)
        self.assertIn("Nouvelle demande d", data["html"])

        n = Notification.objects.filter(recipient=self.admin).first()
        r = self.client.get(reverse("approvals:notification_open", args=[n.pk]))
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r["Location"].endswith(n.url))
        n.refresh_from_db()
        self.assertTrue(n.is_read)

        r = self.client.post(
            reverse("approvals:notification_read_all"), HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )
        self.assertEqual(r.json()["count"], 0)

    def test_cannot_open_someone_elses_notification(self):
        services.submit_request(self.agent, R.KIND_CREATE, proposed_title="A")
        n = Notification.objects.filter(recipient=self.admin).first()
        self.client.force_login(self.agent)
        self.assertEqual(self.client.get(reverse("approvals:notification_open", args=[n.pk])).status_code, 404)

    def test_bell_renders_on_pages_for_every_role(self):
        for u in (self.admin, self.agent, self.staff):
            self.client.force_login(u)
            page = self.client.get(reverse("formations:formation_list"))
            self.assertContains(page, 'id="bellBtn"')

    def test_agent_ui_buttons(self):
        self.client.force_login(self.agent)
        page = self.client.get(reverse("formations:formation_list"))
        self.assertContains(page, "Demander une formation")
        self.assertNotContains(page, reverse("formations:formation_create"))
        detail = self.client.get(reverse("formations:formation_detail", args=[self.formation.pk]))
        self.assertContains(detail, "Demander la modification")
        self.assertNotContains(detail, "Effacer toutes les sessions")
        services.submit_request(self.agent, R.KIND_EDIT, formation=self.formation)
        detail = self.client.get(reverse("formations:formation_detail", args=[self.formation.pk]))
        self.assertContains(detail, "en attente")

    def test_request_pages_access(self):
        req = services.submit_request(self.agent, R.KIND_CREATE, proposed_title="A")
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(reverse("approvals:request_detail", args=[req.pk])).status_code, 302)
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(reverse("approvals:request_list")), "A")
        self.client.force_login(self.agent)
        self.assertEqual(self.client.get(reverse("approvals:request_detail", args=[req.pk])).status_code, 200)


from django.core.mail.backends.base import BaseEmailBackend  # noqa: E402


class BrokenBackend(BaseEmailBackend):
    def send_messages(self, email_messages):
        raise ConnectionError("smtp down")
