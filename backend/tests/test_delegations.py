from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import engine
from app.models import Audit, ClientMembership, Delegation


def test_isolation_and_project_delegation(browser, workspace):
    owner, member, foreign = browser("owner"), browser("member"), browser("foreign")
    base = f"/api/v1/projects/{workspace['north-1']}"
    other = f"/api/v1/projects/{workspace['north-2']}"
    url = base + f"/approval-delegations/{workspace['member_membership']}"

    def authority(client, project=base):
        return client.get(project + "/approval-authority").json()["data"]["has_binding_authority"]

    profile = f"/api/v1/clients/{workspace['north']}?portal=agency"
    assert browser("manager").get(profile).status_code == 200
    assert foreign.get(profile).status_code == 403
    assert authority(owner)
    assert not authority(member)
    assert foreign.get(f"/api/v1/clients/{workspace['north']}").status_code == 404
    assert foreign.get(f"/api/v1/clients/{workspace['north']}/projects").status_code == 404
    assert foreign.put(url).status_code == 404
    assert (
        owner.put(base + f"/approval-delegations/{workspace['foreign_membership']}").status_code
        == 404
    )
    assert member.get(base + "/approval-delegations").status_code == 403
    assert owner.put(url).status_code == 204
    assert owner.put(url).status_code == 204
    assert authority(member)
    assert not authority(member, other)
    assert member.put(url).status_code == 403
    assert member.delete(url).status_code == 403
    assert owner.delete(url).status_code == 204
    assert owner.delete(url).status_code == 204
    assert not authority(member)
    assert owner.put(url).status_code == 204
    with Session(engine()) as db, db.begin():
        assert db.scalar(select(func.count()).select_from(Audit)) == 3
        db.get(ClientMembership, workspace["member_membership"]).is_active = False
    assert member.get(base + "/approval-authority").status_code == 404
    assert owner.put(url).status_code == 403
    with Session(engine()) as db, db.begin():
        db.get(ClientMembership, workspace["member_membership"]).is_active = True
        assert (
            db.scalar(
                select(func.count())
                .select_from(Audit)
                .where(Audit.action == "delegation.invalidated")
            )
            == 1
        )
    assert not authority(member)
    with Session(engine()) as db, pytest.raises(IntegrityError), db.begin():
        db.add(
            Delegation(
                client_id=workspace["north"],
                project_id=workspace["south-1"],
                grantee_membership_id=workspace["member_membership"],
                granted_by_membership_id=workspace["owner_membership"],
            )
        )


def test_concurrent_grants_have_one_effect(browser, workspace):
    clients = (browser("owner"), browser("owner"))
    barrier = Barrier(2)
    url = f"/api/v1/projects/{workspace['north-1']}/approval-delegations/{workspace['member_membership']}"

    def grant(client):
        barrier.wait(timeout=15)
        return client.put(url).status_code

    with ThreadPoolExecutor(2) as pool:
        assert list(pool.map(grant, clients)) == [204, 204]
    with Session(engine()) as db:
        assert db.scalar(select(func.count()).select_from(Delegation)) == 1
        assert db.scalar(select(func.count()).select_from(Audit)) == 1
