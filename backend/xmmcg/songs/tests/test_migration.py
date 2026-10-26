"""Exercise the actual migration graph against historical rows in an isolated database."""

import os
from pathlib import Path
import subprocess
import sys
from django.test import SimpleTestCase


class MigrationTests(SimpleTestCase):
    def test_legacy_data_moves_without_cascading_loss(self):
        script = r"""
import django
django.setup()
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone
from datetime import timedelta
executor = MigrationExecutor(connection)
old_targets = [('songs', '0001_initial'), ('users', '0002_userprofile_preferred_name')]
executor.migrate(old_targets)
apps = executor.loader.project_state(old_targets).apps
User = apps.get_model('auth', 'User')
u1 = User.objects.create(username='p1')
u2 = User.objects.create(username='p2')
u3 = User.objects.create(username='reviewer')
apps.get_model('users', 'UserProfile').objects.create(user_id=u1.pk, token=500)
phase = apps.get_model('songs', 'CompetitionPhase').objects.create(name='old', phase_key='mapping2', start_time=timezone.now(), end_time=timezone.now()+timedelta(days=1))
round = apps.get_model('songs', 'BiddingRound').objects.create(name='round', bidding_type='chart', competition_phase_id=phase.pk)
song = apps.get_model('songs', 'Song').objects.create(user_id=u1.pk, title='original song', audio_file='old/song.mp3', audio_hash='abc', file_size=4)
Chart = apps.get_model('songs', 'Chart')
part = Chart.objects.create(user_id=u1.pk, song_id=song.pk, bidding_round_id=round.pk, status='part_submitted', chart_file='old/part.txt')
final = Chart.objects.create(user_id=u2.pk, song_id=song.pk, bidding_round_id=round.pk, status='final_submitted', part_one_chart_id=part.pk, is_part_one=False, chart_file='old/final.txt')
allocation = apps.get_model('songs', 'PeerReviewAllocation').objects.create(reviewer_id=u3.pk, chart_id=final.pk, bidding_round_id=round.pk, status='completed')
Review = apps.get_model('songs', 'PeerReview')
Review.objects.create(allocation_id=allocation.pk, reviewer_id=u3.pk, chart_id=final.pk, score=20, comment=None)
Review.objects.create(reviewer_id=u3.pk, chart_id=final.pk, score=30, comment='newer score')
executor = MigrationExecutor(connection)
executor.migrate(executor.loader.graph.leaf_nodes())
from songs.models import Chart, LegacyRecord, PeerReview, PeerReviewAllocation, CompetitionPhase
assert Chart.objects.count() == 2
assert Chart.objects.get(pk=part.pk).status == 'archived'
chart = Chart.objects.get(pk=final.pk)
assert chart.title == 'original song'
assert chart.chart_file.name == 'old/final.txt'
assert set(chart.contributors.values_list('pk', flat=True)) == {u1.pk, u2.pk}
assert len(set(Chart.objects.values_list('submission_key', flat=True))) == 2
assert chart.source_song_id == song.pk
assert PeerReview.objects.count() == 1
assert PeerReview.objects.get().score == 30
assert PeerReviewAllocation.objects.count() == 1
assert LegacyRecord.objects.filter(kind='PeerReview').count() == 2
assert LegacyRecord.objects.get(kind='UserTokens').data['token'] == 500
assert CompetitionPhase.objects.get().kind == 'display'
assert 'songs_bid' not in connection.introspection.table_names()
print('migration verified')
"""
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=Path(__file__).resolve().parents[2],
            env={**os.environ, "DJANGO_SETTINGS_MODULE": "xmmcg.test_settings"},
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("migration verified", result.stdout)
