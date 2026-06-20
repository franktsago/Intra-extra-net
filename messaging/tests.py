from django.test import TestCase
from django.urls import reverse

from accounts.models import Role, User
from messaging.models import allowed_recipients, can_message


class MessageEditTest(TestCase):
    """Modification d'un message envoyé : expéditeur uniquement, dans les 10 min."""

    @classmethod
    def setUpTestData(cls):
        cls.a = User.objects.create_user("ed_a", password="x", role=Role.EMPLOYE)
        cls.b = User.objects.create_user("ed_b", password="x", role=Role.EMPLOYE)

    def _msg(self, **extra):
        from messaging.models import Message
        return Message.objects.create(sender=self.a, recipient=self.b, body="Original", **extra)

    def test_sender_can_edit_within_window(self):
        m = self._msg()
        self.client.force_login(self.a)
        r = self.client.post(reverse("messaging:message_edit", args=[m.pk]), {"body": "Corrigé"})
        self.assertEqual(r.status_code, 302)
        m.refresh_from_db()
        self.assertEqual(m.body, "Corrigé")
        self.assertIsNotNone(m.edited_at)

    def test_recipient_cannot_edit(self):
        m = self._msg()
        self.client.force_login(self.b)
        r = self.client.post(reverse("messaging:message_edit", args=[m.pk]), {"body": "Pirate"})
        self.assertEqual(r.status_code, 403)
        m.refresh_from_db()
        self.assertEqual(m.body, "Original")

    def test_edit_blocked_after_10_minutes(self):
        from datetime import timedelta
        from django.utils import timezone
        m = self._msg()
        m.created_at = timezone.now() - timedelta(minutes=11)
        m.save(update_fields=["created_at"])
        self.assertFalse(m.within_edit_window)
        self.client.force_login(self.a)
        self.client.post(reverse("messaging:message_edit", args=[m.pk]), {"body": "Trop tard"})
        m.refresh_from_db()
        self.assertEqual(m.body, "Original")   # inchangé : délai dépassé

    def test_group_message_edit(self):
        from messaging.models import ChatGroup, GroupMessage
        grp = ChatGroup.objects.create(name="G")
        grp.members.add(self.a, self.b)
        gm = GroupMessage.objects.create(group=grp, sender=self.a, body="Salut")
        self.client.force_login(self.a)
        self.client.post(reverse("messaging:group_message_edit", args=[gm.pk]), {"body": "Bonjour"})
        gm.refresh_from_db()
        self.assertEqual(gm.body, "Bonjour")
        self.assertIsNotNone(gm.edited_at)


class MessageSignalingTest(TestCase):
    """Un message reçu se signale par un badge (Messagerie / Discussions),
    jamais par une notification (cloche)."""

    @classmethod
    def setUpTestData(cls):
        cls.a = User.objects.create_user("alice", password="x", role=Role.EMPLOYE)
        cls.b = User.objects.create_user("bob", password="x", role=Role.EMPLOYE)

    def test_direct_message_badges_not_notification(self):
        from messaging.models import unread_count
        from notifications.models import Notification
        self.client.force_login(self.a)
        r = self.client.post(reverse("messaging:thread", args=[self.b.pk]), {"body": "Salut Bob"})
        self.assertEqual(r.status_code, 302)
        # Badge Messagerie pour Bob = 1, et AUCUNE notification cloche.
        self.assertEqual(unread_count(self.b), 1)
        self.assertEqual(Notification.objects.filter(recipient=self.b).count(), 0)

    def test_group_message_badges_not_notification(self):
        from messaging.models import get_general_group, unread_chat_count
        from notifications.models import Notification
        get_general_group()  # ajoute tous les internes (alice, bob)
        self.client.force_login(self.a)
        from messaging.models import ChatGroup
        grp = ChatGroup.objects.get(is_general=True)
        r = self.client.post(reverse("messaging:group", args=[grp.pk]), {"body": "Bonjour l'équipe"})
        self.assertEqual(r.status_code, 302)
        # Badge Discussions pour Bob ≥ 1, et AUCUNE notification cloche.
        self.assertGreaterEqual(unread_chat_count(self.b), 1)
        self.assertEqual(Notification.objects.filter(recipient=self.b).count(), 0)


class MessagingScopeTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.mgr = User.objects.create_user("mgr", password="x", role=Role.MANAGER)
        cls.emp = User.objects.create_user("emp", password="x", role=Role.EMPLOYE)
        cls.client_u = User.objects.create_user("cli", password="x", role=Role.CLIENT)

    def test_employee_cannot_message_client(self):
        self.assertFalse(can_message(self.emp, self.client_u))
        ids = set(allowed_recipients(self.emp).values_list("id", flat=True))
        self.assertNotIn(self.client_u.id, ids)   # le client n'apparaît pas
        self.assertIn(self.mgr.id, ids)            # mais les internes oui

    def test_manager_can_message_client(self):
        self.assertTrue(can_message(self.mgr, self.client_u))


class MessagingActionsTest(TestCase):
    """Suppression de messages/conversations/groupes façon WhatsApp."""

    @classmethod
    def setUpTestData(cls):
        cls.a = User.objects.create_user("alpha", password="x", role=Role.EMPLOYE)
        cls.b = User.objects.create_user("beta", password="x", role=Role.EMPLOYE)

    def test_sender_deletes_own_direct_message(self):
        from messaging.models import Message
        m = Message.objects.create(sender=self.a, recipient=self.b, body="hello")
        self.client.force_login(self.a)
        r = self.client.post(reverse("messaging:message_delete", args=[m.pk]))
        self.assertEqual(r.status_code, 302)
        m.refresh_from_db()
        self.assertTrue(m.deleted_for_all)   # trace conservée pour tout le monde
        self.assertEqual(m.body, "")

    def test_recipient_can_delete_for_self_only(self):
        from messaging.models import Message
        m = Message.objects.create(sender=self.a, recipient=self.b, body="hi")
        self.client.force_login(self.b)
        self.client.post(reverse("messaging:message_delete_me", args=[m.pk]))
        m.refresh_from_db()
        self.assertFalse(m.deleted_for_all)            # pas supprimé pour tous
        self.assertIn(self.b, m.deleted_for.all())      # seulement pour moi

    def test_recipient_cannot_delete_others_message(self):
        from messaging.models import Message
        m = Message.objects.create(sender=self.a, recipient=self.b, body="hi")
        self.client.force_login(self.b)  # destinataire non admin
        self.assertEqual(self.client.post(
            reverse("messaging:message_delete", args=[m.pk])).status_code, 403)
        self.assertTrue(Message.objects.filter(pk=m.pk).exists())

    def test_delete_conversation_is_per_user(self):
        """Effacer une conversation ne la supprime que pour soi : l'autre la garde."""
        from messaging.models import ConversationClear, Message
        Message.objects.create(sender=self.a, recipient=self.b, body="souvenir")
        self.client.force_login(self.a)
        self.client.post(reverse("messaging:thread_delete", args=[self.b.pk]))
        # Rien n'est supprimé physiquement ; une césure d'historique est posée pour A.
        self.assertEqual(Message.objects.count(), 1)
        self.assertTrue(ConversationClear.objects.filter(user=self.a, other=self.b).exists())
        # A ne voit plus l'historique effacé…
        r = self.client.get(reverse("messaging:inbox"))
        self.assertNotContains(r, "souvenir")
        # …mais B conserve toute la conversation.
        self.client.force_login(self.b)
        r = self.client.get(reverse("messaging:inbox"))
        self.assertContains(r, "souvenir")

    def test_group_admin_deletes_and_manages(self):
        from messaging.models import ChatGroup, GroupMessage
        self.client.force_login(self.a)
        g = ChatGroup.objects.create(name="Projet X", created_by=self.a)
        g.members.add(self.a, self.b)
        msg = GroupMessage.objects.create(group=g, sender=self.b, body="coucou")
        # L'admin (créateur) peut supprimer pour tous le message d'un autre.
        self.assertEqual(self.client.post(
            reverse("messaging:group_message_delete", args=[msg.pk])).status_code, 302)
        msg.refresh_from_db()
        self.assertTrue(msg.deleted_for_all)
        # Retirer un membre.
        self.client.post(reverse("messaging:group_member_remove", args=[g.pk, self.b.pk]))
        self.assertNotIn(self.b, g.members.all())
        # Supprimer le groupe.
        self.client.post(reverse("messaging:group_delete", args=[g.pk]))
        self.assertFalse(ChatGroup.objects.filter(pk=g.pk).exists())

    def test_non_admin_cannot_delete_group(self):
        from messaging.models import ChatGroup
        g = ChatGroup.objects.create(name="Privé", created_by=self.a)
        g.members.add(self.a, self.b)
        self.client.force_login(self.b)
        self.assertEqual(self.client.post(
            reverse("messaging:group_delete", args=[g.pk])).status_code, 403)
        self.assertTrue(ChatGroup.objects.filter(pk=g.pk).exists())

    def test_general_group_cannot_be_deleted(self):
        from messaging.models import get_general_group
        g = get_general_group()
        admin = User.objects.create_superuser("suadmin", password="x", role=Role.ADMIN)
        self.client.force_login(admin)
        self.assertEqual(self.client.post(
            reverse("messaging:group_delete", args=[g.pk])).status_code, 403)

    def test_voice_attachment_is_audio(self):
        from messaging.models import Message
        from django.core.files.uploadedfile import SimpleUploadedFile
        import tempfile
        from django.test import override_settings
        with override_settings(MEDIA_ROOT=tempfile.mkdtemp()):
            m = Message.objects.create(sender=self.a, recipient=self.b,
                attachment=SimpleUploadedFile("voix-123.webm", b"RIFF", content_type="audio/webm"))
            self.assertTrue(m.is_audio)
            self.assertFalse(m.is_video)


class MessagingWhatsAppFeaturesTest(TestCase):
    """Réponse (citation) et réactions emoji."""

    @classmethod
    def setUpTestData(cls):
        cls.a = User.objects.create_user("waA", password="x", role=Role.EMPLOYE)
        cls.b = User.objects.create_user("waB", password="x", role=Role.EMPLOYE)

    def test_reply_quotes_message(self):
        from messaging.models import Message
        orig = Message.objects.create(sender=self.b, recipient=self.a, body="Question ?")
        self.client.force_login(self.a)
        self.client.post(reverse("messaging:thread", args=[self.b.pk]),
                         {"body": "Réponse", "reply_to": orig.pk})
        rep = Message.objects.get(body="Réponse")
        self.assertEqual(rep.reply_to_id, orig.pk)

    def test_reaction_toggle(self):
        from messaging.models import Message, Reaction
        m = Message.objects.create(sender=self.a, recipient=self.b, body="hi")
        self.client.force_login(self.b)
        url = reverse("messaging:react", args=["d", m.pk])
        self.client.post(url, {"emoji": "👍"})
        self.assertEqual(Reaction.objects.filter(message=m, emoji="👍").count(), 1)
        # même emoji → retiré
        self.client.post(url, {"emoji": "👍"})
        self.assertEqual(Reaction.objects.filter(message=m).count(), 0)
        # autre emoji → remplacé (un seul par utilisateur)
        self.client.post(url, {"emoji": "❤️"})
        self.client.post(url, {"emoji": "😂"})
        self.assertEqual(Reaction.objects.filter(message=m).count(), 1)
        self.assertEqual(Reaction.objects.get(message=m).emoji, "😂")

    def test_outsider_cannot_react(self):
        from messaging.models import Message
        c = User.objects.create_user("waC", password="x", role=Role.EMPLOYE)
        m = Message.objects.create(sender=self.a, recipient=self.b, body="x")
        self.client.force_login(c)
        self.assertEqual(self.client.post(
            reverse("messaging:react", args=["d", m.pk]), {"emoji": "👍"}).status_code, 403)


class MessagingPinTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.a = User.objects.create_user("pinA", password="x", role=Role.EMPLOYE)
        cls.b = User.objects.create_user("pinB", password="x", role=Role.EMPLOYE)

    def test_pin_message_and_max_three(self):
        from messaging.models import Message
        msgs = [Message.objects.create(sender=self.a, recipient=self.b, body=f"m{i}") for i in range(4)]
        self.client.force_login(self.a)
        for i in range(3):
            self.client.post(reverse("messaging:pin_message", args=["d", msgs[i].pk]))
        self.assertEqual(Message.objects.filter(is_pinned=True).count(), 3)
        # 4e épingle refusée (max 3)
        self.client.post(reverse("messaging:pin_message", args=["d", msgs[3].pk]))
        self.assertEqual(Message.objects.filter(is_pinned=True).count(), 3)
        msgs[3].refresh_from_db(); self.assertFalse(msgs[3].is_pinned)
        # désépingler
        self.client.post(reverse("messaging:pin_message", args=["d", msgs[0].pk]))
        self.assertEqual(Message.objects.filter(is_pinned=True).count(), 2)

    def test_pin_conversation_sorts_first(self):
        from messaging.models import Message, ConversationPin
        c = User.objects.create_user("pinC", password="x", role=Role.EMPLOYE)
        Message.objects.create(sender=self.a, recipient=self.b, body="old")
        Message.objects.create(sender=self.a, recipient=c, body="recent")
        self.client.force_login(self.a)
        # épingle la conversation la plus ancienne (avec b)
        self.client.post(reverse("messaging:pin_conversation", args=["u%d" % self.b.pk]))
        self.assertTrue(ConversationPin.objects.filter(user=self.a, other=self.b).exists())
        r = self.client.get(reverse("messaging:inbox"), SERVER_NAME="127.0.0.1")
        items = r.context["items"]
        self.assertTrue(items[0]["pinned"])
        self.assertEqual(items[0]["user"], self.b)  # épinglée en tête malgré l'ancienneté


class NotificationDeleteTest(TestCase):
    def test_user_deletes_own_notification(self):
        from notifications.models import Notification, notify
        u = User.objects.create_user("notifu", password="x", role=Role.EMPLOYE)
        n = notify(u, "Test", "msg")
        self.client.force_login(u)
        self.client.post(reverse("notifications:delete", args=[n.pk]))
        self.assertFalse(Notification.objects.filter(pk=n.pk).exists())

    def test_cannot_delete_others_notification(self):
        from notifications.models import Notification, notify
        u = User.objects.create_user("nu1", password="x", role=Role.EMPLOYE)
        other = User.objects.create_user("nu2", password="x", role=Role.EMPLOYE)
        n = notify(u, "Privé", "x")
        self.client.force_login(other)
        self.assertEqual(self.client.post(reverse("notifications:delete", args=[n.pk])).status_code, 404)
        self.assertTrue(Notification.objects.filter(pk=n.pk).exists())

    def test_clear_all(self):
        from notifications.models import Notification, notify
        u = User.objects.create_user("nclear", password="x", role=Role.EMPLOYE)
        for i in range(3):
            notify(u, f"n{i}", "x")
        self.client.force_login(u)
        self.client.post(reverse("notifications:clear"))
        self.assertEqual(Notification.objects.filter(recipient=u).count(), 0)


class MessagingRealtimeTest(TestCase):
    """Polling : nouveaux messages, indicateur de saisie, présence."""

    @classmethod
    def setUpTestData(cls):
        cls.a = User.objects.create_user("rtA", password="x", role=Role.EMPLOYE)
        cls.b = User.objects.create_user("rtB", password="x", role=Role.EMPLOYE)

    def test_poll_returns_new_messages(self):
        from messaging.models import Message
        import json
        m = Message.objects.create(sender=self.b, recipient=self.a, body="coucou")
        self.client.force_login(self.a)
        r = self.client.get(reverse("messaging:conv_poll", args=["d", self.b.pk]) + "?after=0")
        data = json.loads(r.content)
        ids = [x["id"] for x in data["messages"]]
        self.assertIn(m.id, ids)
        # après le dernier id → plus rien
        r2 = self.client.get(reverse("messaging:conv_poll", args=["d", self.b.pk]) + f"?after={m.id}")
        self.assertEqual(json.loads(r2.content)["messages"], [])

    def test_typing_indicator(self):
        import json
        self.client.force_login(self.a)
        self.client.post(reverse("messaging:typing_ping", args=["d", self.b.pk]))
        # B interroge → voit A en train d'écrire
        self.client.force_login(self.b)
        r = self.client.get(reverse("messaging:conv_poll", args=["d", self.a.pk]) + "?after=0")
        self.assertTrue(json.loads(r.content)["typing"])


class MessagingCallFlowTest(TestCase):
    """Flux d'appel : démarrage (sonne), entrant, réponse, fin (journalisé)."""

    @classmethod
    def setUpTestData(cls):
        cls.a = User.objects.create_user("cfA", password="x", role=Role.EMPLOYE)
        cls.b = User.objects.create_user("cfB", password="x", role=Role.EMPLOYE)

    def test_full_call_flow(self):
        import json
        from messaging.models import Call, Message
        # A démarre l'appel
        self.client.force_login(self.a)
        r = self.client.get(reverse("messaging:call_start", args=["d", self.b.pk, "video"]))
        self.assertEqual(r.status_code, 302)
        call = Call.objects.latest("id")
        self.assertEqual(call.status, "RINGING")
        # B voit l'appel entrant
        self.client.force_login(self.b)
        inc = json.loads(self.client.get(reverse("messaging:incoming_call")).content)
        self.assertIsNotNone(inc["call"])
        self.assertEqual(inc["call"]["id"], call.pk)
        # B répond (ouvre la salle) → en cours
        self.client.get(reverse("messaging:call", args=[call.pk]))
        call.refresh_from_db()
        self.assertEqual(call.status, "ONGOING")
        # Fin d'appel → terminé + message journal
        self.client.post(reverse("messaging:call_end", args=[call.pk]))
        call.refresh_from_db()
        self.assertEqual(call.status, "COMPLETED")
        self.assertTrue(Message.objects.filter(body__startswith="📞", body__icontains="terminé").exists())

    def test_decline(self):
        from messaging.models import Call, Message
        self.client.force_login(self.a)
        self.client.get(reverse("messaging:call_start", args=["d", self.b.pk, "audio"]))
        call = Call.objects.latest("id")
        self.client.force_login(self.b)
        self.client.post(reverse("messaging:call_decline", args=[call.pk]))
        call.refresh_from_db()
        self.assertEqual(call.status, "DECLINED")
        self.assertTrue(Message.objects.filter(body__icontains="refusé").exists())

    def test_missed_when_stale(self):
        from datetime import timedelta
        from django.utils import timezone
        from messaging.models import Call
        from messaging.views import _expire_stale_calls
        self.client.force_login(self.a)
        self.client.get(reverse("messaging:call_start", args=["d", self.b.pk, "video"]))
        call = Call.objects.latest("id")
        call.created_at = timezone.now() - timedelta(seconds=60)
        call.save(update_fields=["created_at"])
        _expire_stale_calls()
        call.refresh_from_db()
        self.assertEqual(call.status, "MISSED")


class MessagingDeleteScopeTest(TestCase):
    """Suppression : pour tous (expéditeur/admin) vs pour soi (membre lambda) + trace."""

    @classmethod
    def setUpTestData(cls):
        from messaging.models import ChatGroup
        cls.admin_u = User.objects.create_user("gadminu", password="x", role=Role.EMPLOYE)
        cls.sender = User.objects.create_user("gsender", password="x", role=Role.EMPLOYE)
        cls.member = User.objects.create_user("gmember", password="x", role=Role.EMPLOYE)
        cls.g = ChatGroup.objects.create(name="Equipe", created_by=cls.admin_u)
        cls.g.members.add(cls.admin_u, cls.sender, cls.member)

    def test_member_cannot_delete_for_all_but_can_for_self(self):
        from messaging.models import GroupMessage
        m = GroupMessage.objects.create(group=self.g, sender=self.sender, body="hi")
        self.client.force_login(self.member)
        # Pour tout le monde → refusé (ni expéditeur ni admin)
        self.assertEqual(self.client.post(
            reverse("messaging:group_message_delete", args=[m.pk])).status_code, 403)
        m.refresh_from_db(); self.assertFalse(m.deleted_for_all)
        # Pour moi → autorisé, laisse une trace côté membre
        self.client.post(reverse("messaging:group_message_delete_me", args=[m.pk]))
        self.assertIn(self.member, m.deleted_for.all())
        self.assertFalse(m.deleted_for_all)

    def test_admin_deletes_for_all_leaves_trace(self):
        from messaging.models import GroupMessage
        m = GroupMessage.objects.create(group=self.g, sender=self.sender, body="coucou")
        self.client.force_login(self.admin_u)  # créateur = admin du groupe
        self.client.post(reverse("messaging:group_message_delete", args=[m.pk]))
        m.refresh_from_db()
        self.assertTrue(m.deleted_for_all)   # trace pour tout le monde
        self.assertEqual(m.body, "")


class MessageForwardTest(TestCase):
    """Transfert d'un message vers une autre conversation, avec mention « Transféré »."""

    @classmethod
    def setUpTestData(cls):
        cls.a = User.objects.create_user("fa", password="x", role=Role.EMPLOYE)
        cls.b = User.objects.create_user("fb", password="x", role=Role.EMPLOYE)
        cls.c = User.objects.create_user("fc", password="x", role=Role.EMPLOYE)

    def _group(self):
        from messaging.models import ChatGroup
        g = ChatGroup.objects.create(name="Projet", created_by=self.a)
        g.members.add(self.a, self.b, self.c)
        return g

    def test_forward_direct_to_direct(self):
        from messaging.models import Message
        src = Message.objects.create(sender=self.a, recipient=self.b, body="bonjour")
        self.client.force_login(self.b)
        r = self.client.post(reverse("messaging:forward", args=["d", src.pk]),
                             {"target": "u%d" % self.c.id})
        self.assertEqual(r.status_code, 302)
        new = Message.objects.filter(sender=self.b, recipient=self.c).first()
        self.assertIsNotNone(new)
        self.assertTrue(new.is_forwarded)
        self.assertEqual(new.body, "bonjour")
        src.refresh_from_db()
        self.assertFalse(src.is_forwarded)  # l'original n'est pas modifié

    def test_forward_direct_to_group(self):
        from messaging.models import GroupMessage, Message
        g = self._group()
        src = Message.objects.create(sender=self.a, recipient=self.b, body="info")
        self.client.force_login(self.a)
        r = self.client.post(reverse("messaging:forward", args=["d", src.pk]),
                             {"target": "g%d" % g.id})
        self.assertEqual(r.status_code, 302)
        new = GroupMessage.objects.filter(group=g, sender=self.a, body="info").first()
        self.assertIsNotNone(new)
        self.assertTrue(new.is_forwarded)

    def test_forward_group_to_direct(self):
        from messaging.models import GroupMessage, Message
        g = self._group()
        src = GroupMessage.objects.create(group=g, sender=self.a, body="annonce")
        self.client.force_login(self.b)
        r = self.client.post(reverse("messaging:forward", args=["g", src.pk]),
                             {"target": "u%d" % self.c.id})
        self.assertEqual(r.status_code, 302)
        new = Message.objects.filter(sender=self.b, recipient=self.c, body="annonce").first()
        self.assertIsNotNone(new)
        self.assertTrue(new.is_forwarded)

    def test_forward_requires_access_to_source(self):
        from messaging.models import Message
        src = Message.objects.create(sender=self.a, recipient=self.b, body="privé")
        self.client.force_login(self.c)  # c n'est ni l'émetteur ni le destinataire
        r = self.client.post(reverse("messaging:forward", args=["d", src.pk]),
                             {"target": "u%d" % self.a.id})
        self.assertEqual(r.status_code, 403)


class GroupAddTracingTest(TestCase):
    """Ajout à un groupe : message système « X a ajouté Y » + notification à l'ajouté."""

    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user("ga", password="x", role=Role.MANAGER)
        cls.newbie = User.objects.create_user("gn", password="x", role=Role.EMPLOYE)

    def test_adding_member_creates_system_message_and_notifies(self):
        from messaging.models import ChatGroup, GroupMessage
        from notifications.models import Notification
        g = ChatGroup.objects.create(name="Équipe", created_by=self.admin)
        g.members.add(self.admin)
        self.client.force_login(self.admin)
        r = self.client.post(reverse("messaging:group_manage", args=[g.pk]),
                             {"action": "add", "members": [self.newbie.pk]})
        self.assertEqual(r.status_code, 302)
        self.assertIn(self.newbie, g.members.all())
        sysmsg = GroupMessage.objects.filter(group=g, is_system=True).first()
        self.assertIsNotNone(sysmsg)
        self.assertIn("a ajouté", sysmsg.body)
        self.assertIn(self.admin.username, sysmsg.body)  # on sait QUI a ajouté
        # La personne ajoutée est prévenue par la cloche.
        self.assertEqual(Notification.objects.filter(recipient=self.newbie).count(), 1)


class GroupAdminRoleTest(TestCase):
    """Un admin de groupe peut nommer / retirer un autre administrateur (#4)."""

    @classmethod
    def setUpTestData(cls):
        cls.creator = User.objects.create_user("gc", password="x", role=Role.MANAGER)
        cls.other = User.objects.create_user("go", password="x", role=Role.EMPLOYE)
        cls.simple = User.objects.create_user("gs", password="x", role=Role.EMPLOYE)

    def _group(self):
        from messaging.models import ChatGroup
        g = ChatGroup.objects.create(name="Comité", created_by=self.creator)
        g.members.add(self.creator, self.other, self.simple)
        return g

    def test_promote_and_demote_admin(self):
        from messaging.models import is_group_admin
        g = self._group()
        self.client.force_login(self.creator)
        # Nommer « other » administrateur.
        self.client.post(reverse("messaging:group_manage", args=[g.pk]),
                         {"action": "promote", "user": self.other.pk})
        self.assertTrue(g.admins.filter(pk=self.other.pk).exists())
        self.assertTrue(is_group_admin(self.other, g))
        # « other » (désormais admin) peut retirer ce rôle.
        self.client.force_login(self.other)
        self.client.post(reverse("messaging:group_manage", args=[g.pk]),
                         {"action": "demote", "user": self.other.pk})
        self.assertFalse(g.admins.filter(pk=self.other.pk).exists())

    def test_promote_notifies_new_admin(self):
        from messaging.models import GroupMessage
        from notifications.models import Notification
        g = self._group()
        self.client.force_login(self.creator)
        self.client.post(reverse("messaging:group_manage", args=[g.pk]),
                         {"action": "promote", "user": self.other.pk})
        # Notification (cloche) dans l'espace du nouvel admin.
        self.assertTrue(Notification.objects.filter(
            recipient=self.other, title="Vous êtes administrateur").exists())
        # Message système visible dans le groupe.
        self.assertTrue(GroupMessage.objects.filter(
            group=g, is_system=True, body__contains="administrateur").exists())

    def test_simple_member_can_view_participants_but_not_manage(self):
        g = self._group()
        self.client.force_login(self.simple)
        # Vue autorisée (#3) : la liste des participants est accessible.
        r = self.client.get(reverse("messaging:group_manage", args=[g.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Participants")
        # Mais une action de gestion est refusée.
        r = self.client.post(reverse("messaging:group_manage", args=[g.pk]),
                             {"action": "promote", "user": self.other.pk})
        self.assertEqual(r.status_code, 403)


class GroupWithClientsTest(TestCase):
    """Le CEO/admin peut créer un groupe mixte avec des clients (#1)."""

    @classmethod
    def setUpTestData(cls):
        cls.ceo = User.objects.create_user("ceo", password="x", role=Role.CEO)
        cls.manager = User.objects.create_user("mg", password="x", role=Role.MANAGER)
        cls.client_u = User.objects.create_user("cl", password="x", role=Role.CLIENT)

    def test_ceo_can_add_client_to_group(self):
        from messaging.models import ChatGroup
        g = ChatGroup.objects.create(name="Projet client", created_by=self.ceo)
        g.members.add(self.ceo)
        self.client.force_login(self.ceo)
        r = self.client.post(reverse("messaging:group_manage", args=[g.pk]),
                             {"action": "add", "members": [self.client_u.pk]})
        self.assertEqual(r.status_code, 302)
        self.assertIn(self.client_u, g.members.all())

    def test_principal_admin_hidden_from_addable(self):
        """L'administrateur principal n'apparaît pas dans la liste d'ajout."""
        from messaging.models import ChatGroup
        boss = User.objects.create_superuser("root", password="x", role=Role.ADMIN)
        g = ChatGroup.objects.create(name="Projet", created_by=self.manager)
        g.members.add(self.manager)
        self.client.force_login(self.manager)
        r = self.client.get(reverse("messaging:group_manage", args=[g.pk]))
        self.assertNotIn(boss, list(r.context["addable"]))

    def test_manager_cannot_add_client_to_group(self):
        from messaging.models import ChatGroup
        g = ChatGroup.objects.create(name="Interne", created_by=self.manager)
        g.members.add(self.manager)
        self.client.force_login(self.manager)
        self.client.post(reverse("messaging:group_manage", args=[g.pk]),
                         {"action": "add", "members": [self.client_u.pk]})
        # Le client n'est PAS ajouté (filtré aux rôles internes).
        self.assertNotIn(self.client_u, g.members.all())

    def test_client_member_can_open_and_post_in_group(self):
        from messaging.models import ChatGroup, GroupMessage
        g = ChatGroup.objects.create(name="Suivi", created_by=self.ceo)
        g.members.add(self.ceo, self.client_u)
        self.client.force_login(self.client_u)
        # Le client peut ouvrir la discussion de groupe…
        r = self.client.get(reverse("messaging:inbox") + "?conv=g%d" % g.pk)
        self.assertEqual(r.status_code, 200)
        # …et y écrire.
        self.client.post(reverse("messaging:group", args=[g.pk]), {"body": "Bonjour l'équipe"})
        self.assertTrue(GroupMessage.objects.filter(group=g, sender=self.client_u, body="Bonjour l'équipe").exists())


class CallSignalTest(TestCase):
    """Signalisation WebRTC d'un appel direct : échange entre participants, isolé."""

    @classmethod
    def setUpTestData(cls):
        cls.a = User.objects.create_user("csA", password="x", role=Role.EMPLOYE)
        cls.b = User.objects.create_user("csB", password="x", role=Role.EMPLOYE)
        cls.c = User.objects.create_user("csC", password="x", role=Role.EMPLOYE)

    def _start_call(self):
        from messaging.models import Call
        self.client.force_login(self.a)
        self.client.get(reverse("messaging:call_start", args=["d", self.b.pk, "audio"]))
        return Call.objects.latest("id")

    def test_signal_exchange_between_participants(self):
        import json
        call = self._start_call()
        # A poste une offre.
        self.client.post(reverse("messaging:call_signal", args=[call.pk]),
                         data=json.dumps({"kind": "offer", "payload": {"sdp": "x"}}),
                         content_type="application/json")
        # B récupère le signal de A.
        self.client.force_login(self.b)
        d = json.loads(self.client.get(reverse("messaging:call_signal", args=[call.pk])).content)
        self.assertEqual(len(d["signals"]), 1)
        self.assertEqual(d["signals"][0]["kind"], "offer")
        self.assertEqual(d["signals"][0]["payload"]["sdp"], "x")
        # A ne voit pas son propre signal (seulement ceux de l'autre pair).
        self.client.force_login(self.a)
        d2 = json.loads(self.client.get(reverse("messaging:call_signal", args=[call.pk])).content)
        self.assertEqual(len(d2["signals"]), 0)

    def test_non_participant_blocked(self):
        call = self._start_call()
        self.client.force_login(self.c)
        r = self.client.get(reverse("messaging:call_signal", args=[call.pk]))
        self.assertEqual(r.status_code, 403)

    def test_direct_call_page_uses_webrtc(self):
        call = self._start_call()
        r = self.client.get(reverse("messaging:call", args=[call.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "RTCPeerConnection")   # page WebRTC native, pas Jitsi


class RealtimeRecipientsTest(TestCase):
    """L'envoi AJAX renvoie les destinataires à « pinguer » en temps réel (MQTT)."""

    @classmethod
    def setUpTestData(cls):
        cls.a = User.objects.create_user("rtA", password="x", role=Role.EMPLOYE)
        cls.b = User.objects.create_user("rtB", password="x", role=Role.EMPLOYE)

    def test_direct_message_returns_recipient(self):
        import json
        self.client.force_login(self.a)
        r = self.client.post(reverse("messaging:thread", args=[self.b.pk]),
                             {"body": "Coucou"}, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        d = json.loads(r.content)
        self.assertTrue(d["ok"])
        self.assertEqual(d["recipients"], [self.b.pk])
        self.assertEqual(d["conv"], "d%d" % self.a.pk)

    def test_group_message_returns_members_except_sender(self):
        import json
        from messaging.models import ChatGroup
        g = ChatGroup.objects.create(name="Equipe", created_by=self.a)
        g.members.add(self.a, self.b)
        self.client.force_login(self.a)
        r = self.client.post(reverse("messaging:group", args=[g.pk]),
                             {"body": "Salut l'équipe"}, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        d = json.loads(r.content)
        self.assertEqual(d["recipients"], [self.b.pk])   # pas l'expéditeur
        self.assertEqual(d["conv"], "g%d" % g.pk)
