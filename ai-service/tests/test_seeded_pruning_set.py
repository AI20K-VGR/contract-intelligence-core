from fixtures.seeded import pruning_eval


def test_same_article_pruning_keeps_every_gold_relation(monkeypatch, capsys):
    assert pruning_eval.main() == 0, capsys.readouterr().out
