import nox

nox.options.default_venv_backend = "uv|virtualenv"


@nox.session
def test(session):
    session.install("-r", "requirements.txt")
    session.install(".")
    session.install("pytest")
    session.run("pytest")


@nox.session
def typeck(session):
    session.install("-r", "requirements.txt")
    session.install(".")
    session.install("mypy")
    session.run("mypy", "src", "tests")


@nox.session
def lint(session):
    session.install("ruff")
    session.run("ruff", "check", ".")
    session.run("ruff", "check", "--select", "I", ".")


@nox.session
def style(session):
    session.install("ruff")
    session.run("ruff", "format", "--diff", ".")
