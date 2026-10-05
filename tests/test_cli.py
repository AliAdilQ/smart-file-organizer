def test_init_and_seed_idempotent(app):
    from app.models import User, OrganizationSession
    runner = app.test_cli_runner()
    assert runner.invoke(args=['init-db']).exit_code == 0
    assert runner.invoke(args=['seed-demo']).exit_code == 0
    with app.app_context():
        count = OrganizationSession.query.count()
        assert User.query.filter_by(username='admin').count() == 1
    assert runner.invoke(args=['seed-demo']).exit_code == 0
    with app.app_context():
        assert OrganizationSession.query.count() == count
