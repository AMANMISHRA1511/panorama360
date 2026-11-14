import os
import tempfile
# Use an isolated SQLite file to avoid requiring MySQL for automated API tests.
os.environ['DATABASE_URL'] = 'sqlite:///' + os.path.join(tempfile.gettempdir(), 'p360_pytest_' + str(os.getpid()) + '.sqlite')
os.environ['SECRET_KEY'] = 'unit-test-secret-key-not-for-production'
