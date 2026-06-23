"""PM service unit tests."""
import unittest
from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, patch

from app import create_app, db
from app.models import (
    ColumnA,
    ProjectA,
    ProjectACustomField,
    TaskA,
    TaskACustomFieldValue,
    User,
)
from app.pm_service import (
    dependency_cycle_exists,
    portfolio_stats_for_projects,
    task_is_complete,
    task_progress_value,
    validate_column_workflow,
    validate_custom_fields_on_close,
)


class PmServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config['TESTING'] = True
        cls.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        cls.ctx = cls.app.app_context()
        cls.ctx.push()
        db.create_all()

    @classmethod
    def tearDownClass(cls):
        db.session.remove()
        db.drop_all()
        cls.ctx.pop()

    def setUp(self):
        db.session.rollback()
        for table in reversed(db.metadata.sorted_tables):
            db.session.execute(table.delete())
        db.session.commit()

    def _make_task(self, title='Task', progress=0, end_date=None, assignees=None):
        owner = User(username='owner', email='owner@test.com', password='x')
        db.session.add(owner)
        db.session.flush()
        p = ProjectA(name='P', owner_id=owner.id)
        db.session.add(p)
        db.session.flush()
        col = ColumnA(project_id=p.id, title='Todo', position=0)
        db.session.add(col)
        db.session.flush()
        t = TaskA(column_id=col.id, title=title, progress=progress, position=0)
        if end_date:
            t.end_date = end_date
        if assignees:
            t.assignees = assignees
        db.session.add(t)
        db.session.commit()
        return p, col, t

    def test_task_progress_from_subtasks(self):
        _, _, t = self._make_task()
        st1 = MagicMock(is_done=True)
        st2 = MagicMock(is_done=False)
        t.subtasks = [st1, st2]
        self.assertEqual(task_progress_value(t), 50)
        self.assertFalse(task_is_complete(t))

    def test_validate_column_workflow_requires_assignee(self):
        _, col, t = self._make_task()
        col.workflow_rules = '{"require_assignee": true}'
        self.assertEqual(validate_column_workflow(t, col), 'This column requires an assignee.')

    def test_validate_custom_fields_on_close(self):
        p, col, t = self._make_task()
        done_col = ColumnA(project_id=p.id, title='Done', position=1)
        db.session.add(done_col)
        cf = ProjectACustomField(project_id=p.id, name='Sign-off', field_type='text', required_on_close=True)
        db.session.add(cf)
        db.session.commit()
        err = validate_custom_fields_on_close(t, done_col)
        self.assertIn('Sign-off', err)
        db.session.add(TaskACustomFieldValue(task_id=t.id, field_id=cf.id, value_text='OK'))
        db.session.commit()
        self.assertIsNone(validate_custom_fields_on_close(t, done_col))

    def test_portfolio_health_red_when_overdue(self):
        p, _, t = self._make_task(end_date=datetime.utcnow() - timedelta(days=2))
        t.progress = 10
        db.session.commit()
        stats = portfolio_stats_for_projects([p])
        self.assertEqual(len(stats), 1)
        self.assertEqual(stats[0]['health'], 'red')
        self.assertGreaterEqual(stats[0]['overdue_count'], 1)

    def test_dependency_cycle_detection(self):
        p, col, t1 = self._make_task('A')
        t2 = TaskA(column_id=col.id, title='B', position=1)
        db.session.add(t2)
        db.session.commit()
        with patch('app.pm_service.TaskADependency') as Dep:
            Dep.query.join.return_value.join.return_value.filter.return_value.all.return_value = []
            self.assertFalse(dependency_cycle_exists(p.id, t1.id, t2.id))


if __name__ == '__main__':
    unittest.main()
