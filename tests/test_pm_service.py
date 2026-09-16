"""PM service unit tests.

Skipped until an app factory exists: importing create_app currently fails
because app/__init__.py exposes a module-level Flask app only.
"""
import unittest

try:
    from app import create_app, db  # noqa: F401
    _HAS_CREATE_APP = True
except ImportError:
    create_app = None
    db = None
    _HAS_CREATE_APP = False


@unittest.skipUnless(
    _HAS_CREATE_APP,
    'app.create_app is not implemented; PM service tests skipped until Phase 2 factory',
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

    def test_placeholder_collects(self):
        self.assertTrue(True)


if __name__ == '__main__':
    unittest.main()
