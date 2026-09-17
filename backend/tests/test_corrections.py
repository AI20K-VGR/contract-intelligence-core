import pytest
from conftest import create_job
from sqlalchemy import select
from test_workflow import drain

from app.models import AnalysisRevision


def send(client, job, target, action, version, correction=None):
    return client.post('/api/v1/review-events', json={
        'job_id': job, 'target_id': target, 'action': action,
        'expected_revision': version, 'reason': 'Checked original evidence',
        'correction': correction,
    }, headers={'Idempotency-Key': f'{action}-{version}'})


def test_correction_reopens_completeness_and_only_dependent_findings(system):
    client, factory, config = system
    dossier, job = create_job(client, annex=True)
    drain(factory, config)
    url = f'/api/v1/dossiers/{dossier}/results'
    before = client.get(url).json()
    for version, target in enumerate(before['review']['unresolved']):
        assert send(client, job, target, 'confirm', version).status_code == 201
    version = len(before['review']['unresolved'])
    amount = next(f for f in before['machine']['facts']
                  if f['type'] == 'amount' and f['source_role'] == 'contract')
    assert send(client, job, amount['id'], 'correct', version,
                {'amount': '120000000', 'currency': 'VND'}).status_code == 201
    after = client.get(url).json()
    assert after['machine'] == before['machine']
    assert after['effective_result_hash'] != after['result_hash']
    finding = after['effective']['findings'][0]
    old_finding = before['machine']['findings'][0]
    assert finding['supersedes'] == old_finding['id']
    assert finding['values_equal'] is True
    assert finding['disposition'] == 'insufficient_evidence'
    assert set(after['review']['unresolved']) == {'completeness', finding['id']}
    assert not after['review']['stale'] and after['review']['blocked']
    assert send(client, job, old_finding['id'], 'confirm', version + 1).status_code == 404
    for target in after['review']['unresolved']:
        version += 1
        assert send(client, job, target, 'confirm', version).status_code == 201
    approved = client.post(f'/api/v1/dossiers/{dossier}/approve',
        json={'expected_revision': version + 1}, headers={'Idempotency-Key': 'approve-corrected'})
    assert approved.status_code == 201, approved.text
    assert approved.json()['result_hash'] == after['effective_result_hash']
    with factory() as db:
        revisions = list(db.scalars(select(AnalysisRevision)))
        assert len(revisions) == 1
        assert revisions[0].result_hash == after['effective_result_hash']


@pytest.mark.parametrize('correction', [
    {'amount': 120000000, 'currency': 'VND'}, {'amount': 'NaN', 'currency': 'VND'},
    {'amount': '-1', 'currency': 'VND'}, {'amount': '1e999999', 'currency': 'VND'},
    {'name': 'wrong type'}, {'amount': '120', 'currency': 'USD'},
    {'amount': '120', 'currency': 'VND', 'citation_ids': ['forged']},
])
def test_invalid_correction_rolls_back(system, correction):
    client, factory, config = system
    dossier, job = create_job(client)
    drain(factory, config)
    url = f'/api/v1/dossiers/{dossier}/results'
    before = client.get(url).json()
    amount = next(f for f in before['machine']['facts'] if f['type'] == 'amount')
    assert send(client, job, amount['id'], 'correct', 0, correction).status_code == 422
    assert client.get(url).json() == before


def test_repeated_correction_keeps_prior_revision_and_unrelated_finding(system):
    client, factory, config = system
    dossier, job = create_job(client, annex=True)
    drain(factory, config)
    url = f'/api/v1/dossiers/{dossier}/results'
    before = client.get(url).json()
    party = next(f for f in before['machine']['facts'] if f['type'] == 'party_a')
    for version, name in enumerate(['First correction', 'Second correction']):
        assert send(client, job, party['id'], 'correct', version, {'name': name}).status_code == 201
    after = client.get(url).json()
    assert after['effective']['findings'] == before['machine']['findings']
    with factory() as db:
        revisions = list(db.scalars(select(AnalysisRevision).order_by(AnalysisRevision.review_version)))
        assert len(revisions) == 2
        assert next(f for f in revisions[0].result['facts'] if f['id'] == party['id'])['normalized'] == {'name': 'First correction'}
    machine = client.get(f'/api/v1/dossiers/{dossier}/facts?view=machine').json()
    effective = client.get(f'/api/v1/dossiers/{dossier}/facts').json()
    assert machine['items'] != effective['items']
