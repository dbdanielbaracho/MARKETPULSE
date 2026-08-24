from app.storage.creator_agreements import CreatorAgreementStore


def test_creator_agreement_is_unusable_until_explicitly_approved(tmp_path):
    store = CreatorAgreementStore(str(tmp_path / "creator.db"))
    item = store.configure(
        creator_id="creator-1",
        agreement_id="agreement-001",
        share_basis_points=1234,
        approved=False,
    )
    assert item.approved is False
    assert item.approved_at is None
    assert store.approved_for_creator("creator-1") is None


def test_approved_agreement_can_be_loaded_and_revoked(tmp_path):
    store = CreatorAgreementStore(str(tmp_path / "creator.db"))
    store.configure(
        creator_id="creator-1",
        agreement_id="agreement-001",
        share_basis_points=2500,
        approved=True,
    )
    approved = store.approved_for_creator("creator-1")
    assert approved is not None
    assert approved.approved is True
    assert approved.approved_at is not None

    store.revoke("creator-1")
    assert store.approved_for_creator("creator-1") is None


def test_creator_agreement_rejects_invalid_or_ambiguous_configuration(tmp_path):
    store = CreatorAgreementStore(str(tmp_path / "creator.db"))

    for value in (-1, 10001, True, 12.5):
        try:
            store.configure(
                creator_id="creator-1",
                agreement_id="agreement-001",
                share_basis_points=value,
            )
        except ValueError:
            pass
        else:
            raise AssertionError(f"invalid share value accepted: {value!r}")

    store.configure(
        creator_id="creator-1",
        agreement_id="agreement-001",
        share_basis_points=1000,
    )
    try:
        store.configure(
            creator_id="creator-1",
            agreement_id="agreement-002",
            share_basis_points=1000,
        )
    except ValueError as exc:
        assert "another agreement" in str(exc)
    else:
        raise AssertionError("creator was silently moved to another agreement")
