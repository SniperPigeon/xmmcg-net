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
from songs.models import Chart, LegacyRecord, PeerReview, PeerReviewAllocation, CompetitionPhase, Competition, Song
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
history = Competition.objects.get()
assert history.name == '历史比赛' and history.status == 'archived'
assert Competition.current() is None
assert set(Chart.objects.values_list('competition_id', flat=True)) == {history.pk}
assert Song.objects.get().competition_id == history.pk
assert CompetitionPhase.objects.get().competition_id == history.pk
assert 'songs_bid' not in connection.introspection.table_names()
assert 'songs_contestsettings' not in connection.introspection.table_names()
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

    def test_single_contest_data_config_and_draws_are_archived_intact(self):
        script = r"""
import django
django.setup()
from datetime import timedelta
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone
executor = MigrationExecutor(connection)
# 用户迁移名称从迁移图获取，避免为无关迁移添加依赖。
targets = [('songs', '0003_alter_announcement_category_and_more')] + [node for node in executor.loader.graph.leaf_nodes() if node[0] == 'users']
executor.migrate(targets)
apps = executor.loader.project_state(targets).apps
get = lambda name: apps.get_model('songs', name)
u1 = apps.get_model('auth', 'User').objects.create(username='原用户')
u2 = apps.get_model('auth', 'User').objects.create(username='原评分者')
get('ContestSettings').objects.create(id=1, submissions_open=False, reviews_open=False, reviews_per_chart=4, max_score='75.50', max_favorites=2)
stage = get('CompetitionPhase').objects.create(name='原阶段', phase_key='songs', kind='song_selection', start_time=timezone.now(), end_time=timezone.now()+timedelta(days=1))
song = get('Song').objects.create(user_id=u1.pk, phase_id=stage.pk, title='原歌曲', audio_file='old/音频.mp3', audio_hash='abc')
chart = get('Chart').objects.create(user_id=u1.pk, source_song_id=song.pk, title='原谱面', designer='原名义', chart_file='old/谱面.txt', net_sync_status='synced', net_url='https://example.com/chart/1')
chart.contributors.add(u1.pk)
allocation = get('PeerReviewAllocation').objects.create(reviewer_id=u2.pk, chart_id=chart.pk)
get('PeerReview').objects.create(reviewer_id=u2.pk, chart_id=chart.pk, allocation_id=allocation.pk, score='42.75', comment='中文评语', favorite=True)
draw = get('SongDraw').objects.create(phase_id=stage.pk, completed_at=timezone.now())
get('SongDrawEntry').objects.create(draw_id=draw.pk, user_id=u2.pk, song_id=song.pk)
get('Announcement').objects.create(title='原公告', content='原公告内容')
get('Banner').objects.create(title='原横幅', content='原横幅内容')
names = ('Chart', 'Song', 'CompetitionPhase', 'PeerReview', 'PeerReviewAllocation', 'SongDraw', 'SongDrawEntry', 'Announcement', 'Banner')
before = {name: list(get(name).objects.order_by('pk').values()) for name in names}
executor = MigrationExecutor(connection)
executor.migrate(executor.loader.graph.leaf_nodes())
apps = executor.loader.project_state(executor.loader.graph.leaf_nodes()).apps
history = get('Competition').objects.get()
assert history.status == 'archived' and history.archived_at is not None
assert history.reviews_per_chart == 4 and str(history.max_score) == '75.50' and history.max_favorites == 2
assert not history.submissions_open and not history.reviews_open
for name in names:
    after = list(get(name).objects.order_by('pk').values())
    for row in after:
        if name in ('Chart', 'Song', 'CompetitionPhase'):
            assert row.pop('competition_id') == history.pk
    assert before[name] == after, name
assert list(get('Chart').objects.get().contributors.values_list('pk', flat=True)) == [u1.pk]
print('edition migration verified')
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
        self.assertIn("edition migration verified", result.stdout)
