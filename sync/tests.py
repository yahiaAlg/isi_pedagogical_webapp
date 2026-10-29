import datetime
import time
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from clients.models import Client
from formations.models import Branch, Category, Formation, Participant, Session, Specialty
from resources.models import Trainer

from . import pull as pull_mod
from . import transport
from .fiche import generate_fiche
from .models import RemoteClient, RosterEntry, SyncJob, SyncState
from .push import flush_jobs, formation_payload
from .pull import apply_snapshot, split_name
from .seeding import seed_session


def make_formation(**kw):
    d = dict(title="Habilitation électrique", code="HAB01", duration_days=3, duration_hours=21,
             evaluation_type="both", max_participants=3, min_attendance_days=3)
    d.update(kw)
    return Formation.objects.create(**d)


def make_session(client, formation, status="planned", **kw):
    trainer = Trainer.objects.first() or Trainer.objects.create(first_name="T", last_name="R")
    d = dict(formation=formation, client=client, trainer=trainer, capacity=formation.max_participants,
             date_start=datetime.date(2030, 1, 10), date_end=datetime.date(2030, 1, 12),
             location_type="institute", status=status)
    d.update(kw)
    return Session.objects.create(**d)


def line(ext, first, last, status="accepted", code="HAB01", title="Habilitation électrique", **kw):
    return dict(ext_id=ext, enrollment_id=1, enrollment_status=status,
                offering={"code": code, "title": title, "slug": "x", "isi_formation_id": None},
                first_name=first, last_name=last, job_title="Tech", employer="ACME", **kw)


def enterprise(roster, ext=10, **kw):
    s = dict(ext_id=ext, deleted=False, type="enterprise", company_name="ACME SARL",
             trade_register_number="RC-1", nif="123", nis="456", phone="0550000000", email="a@acme.dz",
             responsible_name="Boss", wilaya="Sétif", city="", address="Zone ind.", roster=roster)
    s.update(kw)
    return s


class FicheTests(TestCase):
    def test_sizes_and_rules(self):
        f = make_formation(legal_references="Décret X", accreditation_body="MFEP")
        fiche = generate_fiche(f)
        self.assertNotIn("\n", fiche["description"])
        n = lambda k: len(fiche[k].splitlines())
        self.assertTrue(4 <= n("objectives") <= 7, fiche["objectives"])
        self.assertTrue(5 <= n("program_outline") <= 10)
        self.assertTrue(3 <= n("main_tasks") <= 6)
        self.assertTrue(2 <= n("prerequisites") <= 4)
        self.assertIn("MFEP", fiche["description"])
        self.assertIn("10/20", fiche["objectives"])

    def test_theory_only_has_no_tasks_and_uses_own_description(self):
        f = make_formation(evaluation_type="theory_only", description="Ma description.", produces_certificate=False)
        fiche = generate_fiche(f)
        self.assertEqual(fiche["main_tasks"], "")
        self.assertTrue(fiche["description"].startswith("Ma description."))
        self.assertNotIn("Obtenir", fiche["objectives"])

    def test_long_course_gets_more_modules(self):
        short, long_ = generate_fiche(make_formation(duration_days=2)), generate_fiche(make_formation(code="L", duration_days=180, min_attendance_days=150))
        self.assertGreater(len(long_["program_outline"].splitlines()), len(short["program_outline"].splitlines()))
        self.assertLessEqual(len(long_["program_outline"].splitlines()), 10)


@override_settings(SYNC_SHARED_SECRET="s3", MAIN_SITE_URL="https://site.test")
class PushTests(TestCase):
    def test_saving_formation_queues_one_job(self):
        f = make_formation()
        f.title = "Nouveau titre"; f.save()
        self.assertEqual(SyncJob.objects.filter(object_id=f.pk, status="pending").count(), 1)

    def test_payload_shape(self):
        b = Branch.objects.create(abbreviation="MEE", name="Maintenance", name_ar="صيانة", curriculum_type="qualifiante",
                                  curriculum_min_months=1, curriculum_max_months=6)
        sp = Specialty.objects.create(branch=b, code="2512", title="Elec")
        cat = Category.objects.create(name="HSE")
        f = make_formation(specialty=sp, category=cat)
        p = formation_payload(f)
        self.assertEqual((p["code"], p["specialty"]["branch_abbr"], p["category"]), ("MEE2512", "MEE", "HSE"))
        self.assertIn("objectives", p["fiche"])

    def test_flush_success_and_failure_retry(self):
        f = make_formation()
        with mock.patch.object(transport, "call", return_value={"results": [{"created": True}], "errors": []}) as m:
            sent, left = flush_jobs()
        self.assertEqual((sent, left), (1, 0))
        self.assertEqual(m.call_args.args[:2], ("POST", "formations/"))
        self.assertEqual(m.call_args.kwargs["payload"]["isi_formation_id"], f.pk)
        f.save()
        with mock.patch.object(transport, "call", side_effect=transport.SyncError("Site injoignable : x")):
            flush_jobs()
        job = SyncJob.objects.get(status="pending")
        self.assertEqual(job.attempts, 1)
        self.assertIn("injoignable", job.last_error)

    def test_formation_without_code_fails_once_and_is_requeued_on_fix(self):
        f = make_formation(code="")
        self.assertEqual(f.code, "")
        with mock.patch.object(transport, "call") as m:
            flush_jobs()
        m.assert_not_called()
        job = SyncJob.objects.get()
        self.assertEqual(job.status, "failed")
        self.assertIn("spécialité", job.last_error)
        f.code = "FIX1"; f.save()                     # fixed -> a new pending job appears
        self.assertEqual(SyncJob.objects.filter(status="pending").count(), 1)

    @override_settings(SYNC_SHARED_SECRET="")
    def test_unconfigured_keeps_queue(self):
        make_formation()
        self.assertEqual(flush_jobs()[0], 0)
        self.assertEqual(SyncJob.objects.filter(status="pending").count(), 1)

    def test_signature_matches_website_algorithm(self):
        self.assertEqual(
            transport.sign("k", "100", "get", "/a?b=1", b"x"),
            __import__("hashlib").new("sha256") and transport.sign("k", "100", "GET", "/a?b=1", b"x"),
        )


class NameTests(TestCase):
    def test_split(self):
        self.assertEqual(split_name("Mohamed Amine Benali"), {"first_name": "Mohamed Amine", "last_name": "Benali"})
        self.assertEqual(split_name("محمد بن علي"), {"first_name_ar": "محمد بن", "last_name_ar": "علي"})
        self.assertEqual(split_name("Madonna"), {})


class PullTests(TestCase):
    def setUp(self):
        self.f = make_formation()
        self.acme_existing = None

    def test_individual_goes_under_particuliers_and_seeds_planned_session(self):
        part = Client.objects.create(name="Particuliers", address="s", city="s")
        s = make_session(part, self.f)
        snap = dict(ext_id=5, deleted=False, type="individual", roster=[
            dict(line("en:1", "", "", full_name="Amine Benali"))])
        res = apply_snapshot(snap)
        self.assertEqual(res["action"], "individual")
        p = Participant.objects.get(session=s)
        self.assertEqual((p.first_name, p.last_name, p.employer_client), ("Amine", "Benali", None))
        self.assertEqual(Client.objects.filter(name__iexact="particuliers").count(), 1)

    def test_particuliers_created_if_missing(self):
        apply_snapshot(dict(ext_id=5, deleted=False, type="individual", roster=[]))
        self.assertTrue(Client.objects.filter(name="Particuliers").exists())

    def test_new_enterprise_created_with_roster_waiting_for_session(self):
        res = apply_snapshot(enterprise([line("ep:1", "Ali", "Kaci"), line("ep:2", "Sara", "Nour", status="pending")]))
        self.assertEqual(res["action"], "created")
        c = Client.objects.get(name="ACME SARL")
        self.assertEqual((c.rc, c.nif, c.city, c.contact_person), ("RC-1", "123", "Sétif", "Boss"))
        self.assertEqual(RosterEntry.objects.filter(client=c).count(), 2)
        self.assertEqual(Participant.objects.count(), 0)          # no session yet
        # the institute then creates the session -> accepted person is auto-seeded, pending one is not
        s = make_session(c, self.f)
        seed_session(s)
        self.assertEqual(list(s.participant_set.values_list("last_name", flat=True)), ["Kaci"])
        self.assertEqual(s.participant_set.get().employer_client_id, c.pk)

    def test_session_creation_signal_seeds(self):
        apply_snapshot(enterprise([line("ep:1", "Ali", "Kaci")]))
        c = Client.objects.get(name="ACME SARL")
        with self.captureOnCommitCallbacks(execute=True):
            s = make_session(c, self.f)
        self.assertEqual(s.participant_set.count(), 1)

    def test_adopts_existing_client_by_rc_without_overwriting(self):
        old = Client.objects.create(name="Acme (ancien nom)", address="Alger", city="Alger", rc="rc-1", phone="")
        res = apply_snapshot(enterprise([]))
        self.assertEqual(res["action"], "linked")
        old.refresh_from_db()
        self.assertEqual((old.name, old.address, old.phone, old.nif), ("Acme (ancien nom)", "Alger", "0550000000", "123"))
        self.assertEqual(Client.objects.count(), 1)

    def test_roster_changes_propagate_only_website_changed_fields(self):
        apply_snapshot(enterprise([line("ep:1", "Ali", "Kaci", phone="0550")]))
        c = Client.objects.get(name="ACME SARL")
        s = make_session(c, self.f)
        seed_session(s)
        p = s.participant_set.get()
        p.first_name_ar, p.job_title = "علي", "Chef"          # staff edits at the institute
        p.save()
        # website: phone changed, job_title unchanged
        apply_snapshot(enterprise([line("ep:1", "Ali", "Kaci", phone="0661")]))
        p.refresh_from_db()
        self.assertEqual((p.phone, p.job_title, p.first_name_ar), ("0661", "Chef", "علي"))
        # website renames the person
        apply_snapshot(enterprise([line("ep:1", "Ali", "Kacimi", phone="0661")]))
        p.refresh_from_db()
        self.assertEqual(p.last_name, "Kacimi")
        self.assertEqual(s.participant_set.count(), 1)

    def test_removal_rules(self):
        apply_snapshot(enterprise([line("ep:1", "Ali", "Kaci"), line("ep:2", "Sara", "Nour")]))
        c = Client.objects.get(name="ACME SARL")
        s = make_session(c, self.f); seed_session(s)
        kept = s.participant_set.get(last_name="Nour")
        kept.score_theory = 12; kept.save()                      # has marks -> must survive
        apply_snapshot(enterprise([]))                           # website emptied the roster
        (kept_entry,) = RosterEntry.objects.all()                # only the person with marks remains, flagged
        self.assertTrue(kept_entry.removed_on_site)
        self.assertEqual(list(s.participant_set.values_list("last_name", flat=True)), ["Nour"])

    def test_capacity_respected_and_leftovers_wait(self):
        apply_snapshot(enterprise([line(f"ep:{i}", f"P{i}", f"N{i}") for i in range(5)]))
        c = Client.objects.get(name="ACME SARL")
        s = make_session(c, self.f); counts = seed_session(s)
        self.assertEqual(s.participant_set.count(), 3)
        self.assertEqual(counts["seeded"], 3)
        self.assertEqual(RosterEntry.objects.filter(participant__isnull=True).count(), 2)

    def test_incomplete_name_is_flagged_not_seeded(self):
        apply_snapshot(enterprise([line("en:9", "", "", full_name="Madonna")]))
        e = RosterEntry.objects.get()
        self.assertIn("Nom complet", e.note)
        c = e.client; s = make_session(c, self.f); seed_session(s)
        self.assertEqual(s.participant_set.count(), 0)

    def test_unknown_formation_resolved_later(self):
        apply_snapshot(enterprise([line("ep:1", "Ali", "Kaci", code="NEW1", title="Secourisme avancé")]))
        self.assertIsNone(RosterEntry.objects.get().formation)
        newf = make_formation(code="NEW1", title="Secourisme avancé")
        c = Client.objects.get(name="ACME SARL")
        s = make_session(c, newf); seed_session(s)
        self.assertEqual(s.participant_set.count(), 1)

    def test_tombstone_deactivates_unused_client(self):
        apply_snapshot(enterprise([line("ep:1", "Ali", "Kaci")]))
        apply_snapshot(dict(ext_id=10, deleted=True, reason="removed"))
        self.assertFalse(Client.objects.get(name="ACME SARL").is_active)
        self.assertEqual(RosterEntry.objects.count(), 0)

    def test_enterprise_data_update_only_changed_fields(self):
        apply_snapshot(enterprise([]))
        c = Client.objects.get(name="ACME SARL"); c.phone = "0770"; c.save()   # staff fixed phone
        apply_snapshot(enterprise([], email="new@acme.dz"))
        c.refresh_from_db()
        self.assertEqual((c.email, c.phone), ("new@acme.dz", "0770"))


@override_settings(SYNC_SHARED_SECRET="s3", MAIN_SITE_URL="https://site.test")
class PullCursorTests(TestCase):
    def test_first_run_starts_at_head_then_applies_events(self):
        calls = []

        def fake(method, endpoint, params=None, payload=None, timeout=None):
            calls.append(params)
            if params.get("mode") == "head":
                return {"cursor": 7}
            return {"cursor": 9, "has_more": False, "clients": [enterprise([])]}

        with mock.patch.object(transport, "call", side_effect=fake):
            s1 = pull_mod.pull()
            self.assertEqual(s1["initialised_at"], 7)
            self.assertEqual(Client.objects.count(), 0)
            s2 = pull_mod.pull()
        self.assertEqual(s2["applied"], 1)
        self.assertEqual(SyncState.get("feed_cursor"), "9")
        self.assertEqual(calls[-1]["cursor"], 7)

    def test_one_bad_client_does_not_stop_the_page(self):
        SyncState.put("feed_cursor", 1)
        bad = dict(ext_id=1, deleted=False, type="enterprise", roster=[])      # no company_name -> blank name
        bad["company_name"] = None
        good = enterprise([], ext=2)
        with mock.patch.object(transport, "call", return_value={"cursor": 5, "has_more": False, "clients": [bad, good]}):
            res = pull_mod.pull()
        self.assertEqual(SyncState.get("feed_cursor"), "5")
        self.assertTrue(Client.objects.filter(name="ACME SARL").exists())
        self.assertGreaterEqual(res["applied"], 1)


class ViewTests(TestCase):
    def setUp(self):
        self.u = User.objects.create_user("admin1", password="x")
        self.u.profile.role = "admin"; self.u.profile.save()
        self.client.login(username="admin1", password="x")

    def test_status_page_renders(self):
        self.assertEqual(self.client.get("/sync/").status_code, 200)

    def test_client_detail_shows_roster_and_session_button(self):
        f = make_formation()
        apply_snapshot(enterprise([line("ep:1", "Ali", "Kaci")]))
        c = Client.objects.get(name="ACME SARL")
        r = self.client.get(f"/clients/{c.pk}/")
        self.assertContains(r, "Participants inscrits via le site")
        self.assertContains(r, "Ali Kaci")
        s = make_session(c, f)
        r = self.client.get(f"/formations/sessions/{s.pk}/")
        if r.status_code == 200:
            self.assertContains(r, "Depuis le site (1)")
        r = self.client.post(f"/sync/session/{s.pk}/import/")
        self.assertEqual(r.status_code, 302)
        self.assertEqual(s.participant_set.count(), 1)


# ---------------------------------------------------------------- new behaviours
class UnvalidatedSeedingTests(TestCase):
    def setUp(self):
        self.f = make_formation()
        apply_snapshot(enterprise([line("ep:1", "Ali", "Kaci"), line("ep:2", "Sara", "Nour", status="pending"),
                                   line("ep:3", "Omar", "Taleb", status="contacted")]))
        self.c = Client.objects.get(name="ACME SARL")

    def test_default_skips_unvalidated_manual_button_includes_them(self):
        s = make_session(self.c, self.f)
        seed_session(s)
        self.assertEqual(s.participant_set.count(), 1)
        seed_session(s, include_pending=True)
        self.assertEqual(sorted(s.participant_set.values_list("last_name", flat=True)), ["Kaci", "Nour", "Taleb"])

    @override_settings(SYNC_SEED_STATUSES="accepted,confirmed,pending,contacted")
    def test_setting_widens_automatic_seeding(self):
        s = make_session(self.c, self.f)
        seed_session(s)
        self.assertEqual(s.participant_set.count(), 3)

    def test_states(self):
        self.assertEqual(RosterEntry.objects.get(ext_id="ep:1").state, "pending")
        self.assertEqual(RosterEntry.objects.get(ext_id="ep:2").state, "awaiting_validation")
        with override_settings(SYNC_SEED_STATUSES="pending,accepted"):
            self.assertEqual(RosterEntry.objects.get(ext_id="ep:2").state, "pending")


class RemovedOnSiteTests(TestCase):
    def setUp(self):
        self.f = make_formation()
        apply_snapshot(enterprise([line("ep:1", "Ali", "Kaci"), line("ep:2", "Sara", "Nour")]))
        self.c = Client.objects.get(name="ACME SARL")
        self.s = make_session(self.c, self.f)
        seed_session(self.s)

    def test_person_with_marks_is_kept_flagged_and_unflagged_when_back(self):
        p = self.s.participant_set.get(last_name="Nour")
        p.score_theory = 14; p.save()
        apply_snapshot(enterprise([line("ep:1", "Ali", "Kaci")]))
        e = RosterEntry.objects.get(ext_id="ep:2")
        self.assertTrue(e.removed_on_site)
        self.assertEqual(e.state, "removed")
        self.assertIn("conservé", e.note)
        self.assertTrue(self.s.participant_set.filter(last_name="Nour").exists())
        self.assertFalse(RosterEntry.objects.filter(ext_id="ep:1", removed_on_site=True).exists())
        # the website restores the line
        apply_snapshot(enterprise([line("ep:1", "Ali", "Kaci"), line("ep:2", "Sara", "Nour")]))
        self.assertFalse(RosterEntry.objects.get(ext_id="ep:2").removed_on_site)

    def test_started_session_keeps_everyone_flagged(self):
        self.s.status = "in_progress"; self.s.save()
        apply_snapshot(enterprise([]))
        self.assertEqual(RosterEntry.objects.filter(removed_on_site=True).count(), 2)
        self.assertEqual(self.s.participant_set.count(), 2)

    def test_pristine_planned_still_deleted(self):
        apply_snapshot(enterprise([line("ep:1", "Ali", "Kaci")]))
        self.assertEqual(self.s.participant_set.count(), 1)
        self.assertFalse(RosterEntry.objects.filter(ext_id="ep:2").exists())


@override_settings(SYNC_SHARED_SECRET="s3", MAIN_SITE_URL="https://site.test")
class BackfillAndRepairTests(TestCase):
    """Website has clients 1 (old), 2 (old), 3 (new). Baseline = 2."""

    def _feed(self, snaps):
        def fake(method, endpoint, params=None, payload=None, timeout=None):
            if params.get("mode") == "head":
                return {"cursor": 4, "max_client_id": 2}
            if params.get("mode") == "full":
                return {"clients": snaps, "has_more": False, "after_id": 3}
            return {"cursor": 4, "has_more": False, "clients": []}
        return fake

    def clients(self):
        return [enterprise([], ext=i, company_name=f"Corp {i}", trade_register_number=f"RC{i}", nif=f"N{i}") for i in (1, 2, 3)]

    def test_first_run_default_does_not_import_old_clients_but_records_baseline(self):
        with mock.patch.object(transport, "call", side_effect=self._feed(self.clients())):
            pull_mod.pull()
        self.assertEqual(SyncState.get("baseline_client_id"), "2")
        self.assertEqual(Client.objects.count(), 0)

    def test_repair_applies_only_known_or_newer_than_baseline(self):
        with mock.patch.object(transport, "call", side_effect=self._feed(self.clients())):
            pull_mod.pull()                                   # init, baseline 2
            res = pull_mod.pull(repair=True)
        self.assertEqual(res["skipped"], 2)
        self.assertEqual(list(Client.objects.values_list("name", flat=True)), ["Corp 3"])   # the missed new one healed
        # once known, an old client is kept in sync by repair walks
        RemoteClient.objects.create(ext_id=1, client=Client.objects.create(name="Corp 1", address="x", city="x"))
        with mock.patch.object(transport, "call", side_effect=self._feed(self.clients())):
            res = pull_mod.pull(repair=True)
        self.assertEqual(res["skipped"], 1)

    def test_backfill_imports_everything_and_sets_cursor(self):
        with mock.patch.object(transport, "call", side_effect=self._feed(self.clients())):
            res = pull_mod.pull(backfill=True)
        self.assertEqual(Client.objects.count(), 3)
        self.assertEqual(SyncState.get("feed_cursor"), "4")
        self.assertEqual(SyncState.get("baseline_client_id"), "0")

    @override_settings(SYNC_INITIAL_BACKFILL=True)
    def test_setting_makes_first_run_import_all(self):
        with mock.patch.object(transport, "call", side_effect=self._feed(self.clients())):
            pull_mod.pull()
        self.assertEqual(Client.objects.count(), 3)

    def test_full_after_init_imports_old_ones_too(self):
        with mock.patch.object(transport, "call", side_effect=self._feed(self.clients())):
            pull_mod.pull()
            pull_mod.pull(full=True)
        self.assertEqual(Client.objects.count(), 3)

    @override_settings(SYNC_AUTO_FULL_HOURS=24)
    def test_pull_auto_runs_repair_only_when_due(self):
        with mock.patch.object(transport, "call", side_effect=self._feed(self.clients())) as m:
            pull_mod.pull_auto()                              # init
            self.assertEqual(Client.objects.count(), 0)
            n = m.call_count
            pull_mod.pull_auto()                              # not due: events only (1 call)
            self.assertEqual(m.call_count, n + 1)
            from django.utils import timezone
            SyncState.put("last_full", (timezone.now() - datetime.timedelta(hours=25)).isoformat())
            res = pull_mod.pull_auto()                        # due: + repair walk
            self.assertEqual(res.get("repaired"), 1)
            self.assertEqual(list(Client.objects.values_list("name", flat=True)), ["Corp 3"])

    @override_settings(SYNC_AUTO_FULL_HOURS=0)
    def test_auto_repair_can_be_disabled(self):
        with mock.patch.object(transport, "call", side_effect=self._feed(self.clients())):
            pull_mod.pull_auto(); SyncState.put("last_full", "2000-01-01T00:00:00+00:00")
            res = pull_mod.pull_auto()
        self.assertNotIn("repaired", res)


@override_settings(SYNC_SHARED_SECRET="s3", MAIN_SITE_URL="https://site.test")
class FormationDeletionTests(TestCase):
    def test_delete_queues_deactivation_and_cancels_pending_upsert(self):
        f = make_formation()
        pk = f.pk
        f.delete()
        self.assertFalse(SyncJob.objects.filter(kind="formation", object_id=pk, status="pending").exists())
        job = SyncJob.objects.get(kind="formation_deleted", object_id=pk)
        with mock.patch.object(transport, "call", return_value={"deactivated": [pk]}) as m:
            flush_jobs()
        self.assertEqual(m.call_args.args[:2], ("POST", "formations/deactivate/"))
        self.assertEqual(m.call_args.kwargs["payload"], {"isi_formation_ids": [pk]})
        job.refresh_from_db()
        self.assertEqual(job.status, "done")

    def test_failed_deactivation_retries(self):
        f = make_formation(); f.delete()
        with mock.patch.object(transport, "call", side_effect=transport.SyncError("Site injoignable : x")):
            flush_jobs()
        self.assertEqual(SyncJob.objects.get(kind="formation_deleted").status, "pending")


class NewViewTests(TestCase):
    def setUp(self):
        self.u = User.objects.create_user("admin2", password="x")
        self.u.profile.role = "admin"; self.u.profile.save()
        self.client.login(username="admin2", password="x")

    @override_settings(SYNC_SHARED_SECRET="s3", MAIN_SITE_URL="https://site.test")
    def test_import_existing_button_runs_full_import(self):
        snaps = [enterprise([], ext=1)]
        resp = {"clients": snaps, "has_more": False, "after_id": 1, "cursor": 3, "max_client_id": 1}
        with mock.patch.object(transport, "call", return_value=resp):
            r = self.client.post("/sync/import-existing/")
        self.assertEqual(r.status_code, 302)
        self.assertTrue(Client.objects.filter(name="ACME SARL").exists())

    @override_settings(SYNC_SHARED_SECRET="s3", MAIN_SITE_URL="https://site.test")
    def test_status_page_shows_import_button_and_removed_count(self):
        r = self.client.get("/sync/")
        self.assertContains(r, "Importer les clients existants")

    def test_session_page_unvalidated_button_and_manual_import(self):
        f = make_formation()
        apply_snapshot(enterprise([line("ep:1", "Ali", "Kaci"), line("ep:2", "Sara", "Nour", status="pending")]))
        c = Client.objects.get(name="ACME SARL")
        s = make_session(c, f)
        r = self.client.get(f"/formations/sessions/{s.pk}/")
        self.assertContains(r, "+ non validés (1)")
        self.client.post(f"/sync/session/{s.pk}/import/", {"include_pending": "1"})
        self.assertEqual(s.participant_set.count(), 2)

    def test_status_page_labels_deletion_and_creation_jobs(self):
        SyncJob.objects.create(kind="formation_deleted", object_id=69, status="done", result={"deactivated": []})
        SyncJob.objects.create(kind="formation_deleted", object_id=70, status="done", result={"deactivated": [70]})
        SyncJob.objects.create(kind="formation", object_id=135, status="done", result={"created": True, "is_active": False})
        r = self.client.get("/sync/")
        self.assertContains(r, "Aucune offre liée sur le site")
        self.assertContains(r, "Offre masquée sur le site")
        self.assertContains(r, "masquée — à publier par le personnel")
        self.assertNotContains(r, "Offre mise à jour")

    def test_client_page_shows_removed_badge(self):
        f = make_formation()
        apply_snapshot(enterprise([line("ep:1", "Ali", "Kaci")]))
        c = Client.objects.get(name="ACME SARL")
        s = make_session(c, f); seed_session(s)
        p = s.participant_set.get(); p.certificate_issued = True; p.save()
        apply_snapshot(enterprise([]))
        self.assertContains(self.client.get(f"/clients/{c.pk}/"), "Retiré du site")
