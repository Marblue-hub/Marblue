from dataco.cli import parser


def test_commands_are_explicit():
    assert parser().parse_args(['validate']).command == 'validate'
    assert parser().parse_args(['build']).command == 'build'


def test_relative_config_paths_are_resolved_from_project_root(tmp_path, monkeypatch):
    from dataco.settings import ROOT, load_config
    config = tmp_path / 'portable.yaml'
    config.write_text('input: data/raw/example.csv\ndictionary: data/raw/dictionary.csv\n', encoding='utf-8')
    monkeypatch.chdir(tmp_path)
    cfg = load_config(config)
    assert cfg['input'] == ROOT / 'data/raw/example.csv'
    assert cfg['dictionary'] == ROOT / 'data/raw/dictionary.csv'
