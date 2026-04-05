"""
DiffusionBot CLI — Interface en ligne de commande.

Usage:
    python cli.py run diffusion|monitoring|intelligence|analytics
    python cli.py server
    python cli.py status
    python cli.py add-project <slug> <nom> <domaine>
    python cli.py add-platform <slug> <nom> <url> <type> <adapter>
"""

import asyncio
import sys

import click


@click.group()
def main():
    """DiffusionBot — Agent autonome de diffusion SEO."""
    pass


@main.command()
@click.argument("worker", type=click.Choice(["diffusion", "monitoring", "intelligence", "analytics"]))
def run(worker: str):
    """Lance un worker manuellement."""
    from cron.entrypoints import HANDLERS
    click.echo(f"Lancement du worker: {worker}")
    asyncio.run(HANDLERS[worker]())


@main.command()
@click.option("--host", default="0.0.0.0")
@click.option("--port", default=8420)
@click.option("--reload", is_flag=True, default=False)
def server(host: str, port: int, reload: bool):
    """Lance le serveur API + Dashboard."""
    import uvicorn
    click.echo(f"Serveur DiffusionBot sur http://{host}:{port}")
    click.echo(f"Dashboard: http://{host}:{port}/dashboard/")
    click.echo(f"API docs: http://{host}:{port}/docs")
    uvicorn.run("api.app:app", host=host, port=port, reload=reload)


@main.command()
def status():
    """Affiche le statut du systeme."""
    from sqlalchemy import func, select
    from db.engine import SessionLocal
    from db.models import Plateforme, Post, Projet, Contenu

    db = SessionLocal()
    try:
        projets = db.execute(select(func.count(Projet.id)).where(Projet.actif.is_(True))).scalar()
        plateformes = db.execute(select(func.count(Plateforme.id)).where(Plateforme.actif.is_(True))).scalar()
        contenus = db.execute(select(func.count(Contenu.id))).scalar()
        posts_total = db.execute(select(func.count(Post.id))).scalar()
        posts_publies = db.execute(select(func.count(Post.id)).where(Post.statut == "publie")).scalar()
        posts_erreur = db.execute(select(func.count(Post.id)).where(Post.statut == "erreur")).scalar()
        posts_morts = db.execute(select(func.count(Post.id)).where(Post.statut.in_(["supprime", "404"]))).scalar()

        click.echo("=== DiffusionBot Status ===")
        click.echo(f"Projets actifs:      {projets}")
        click.echo(f"Plateformes actives: {plateformes}")
        click.echo(f"Contenus en base:    {contenus}")
        click.echo(f"Posts total:         {posts_total}")
        click.echo(f"  Publies:           {posts_publies}")
        click.echo(f"  Erreurs:           {posts_erreur}")
        click.echo(f"  Morts (404/supp):  {posts_morts}")
    finally:
        db.close()


@main.command("add-project")
@click.argument("slug")
@click.argument("nom")
@click.argument("domaine")
@click.option("--url-base", default=None, help="URL de base (defaut: https://domaine)")
@click.option("--rythme", default=2, help="Posts par jour")
@click.option("--ga4", default=None, help="GA4 property ID")
@click.option("--gsc", default=None, help="GSC site URL")
def add_project(slug, nom, domaine, url_base, rythme, ga4, gsc):
    """Ajoute un projet."""
    from db.engine import SessionLocal
    from db.models import Projet

    db = SessionLocal()
    try:
        projet = Projet(
            slug=slug,
            nom=nom,
            domaine=domaine,
            url_base=url_base or f"https://{domaine}",
            rythme_diffusion_jour=rythme,
            ga4_property_id=ga4,
            gsc_site_url=gsc,
        )
        db.add(projet)
        db.commit()
        click.echo(f"Projet '{nom}' ({slug}) ajoute avec succes.")
    except Exception as e:
        click.echo(f"Erreur: {e}", err=True)
    finally:
        db.close()


@main.command("add-platform")
@click.argument("slug")
@click.argument("nom")
@click.argument("url")
@click.argument("content_type", type=click.Choice(["article", "post_court", "commentaire", "profil", "wiki"]))
@click.option("--da", default=None, type=float, help="Domain Authority")
@click.option("--dofollow/--nofollow", default=True)
@click.option("--difficulte", default="moyen", type=click.Choice(["facile", "moyen", "difficile"]))
def add_platform(slug, nom, url, content_type, da, dofollow, difficulte):
    """Ajoute une plateforme."""
    from db.engine import SessionLocal
    from db.models import Plateforme

    db = SessionLocal()
    try:
        plateforme = Plateforme(
            slug=slug,
            nom=nom,
            url_base=url,
            type_contenu=content_type,
            adapter_class=f"adapters.platforms.{slug}",
            da_actuel=da,
            dofollow=dofollow,
            difficulte_posting=difficulte,
        )
        db.add(plateforme)
        db.commit()
        click.echo(f"Plateforme '{nom}' ({slug}) ajoutee avec succes.")
    except Exception as e:
        click.echo(f"Erreur: {e}", err=True)
    finally:
        db.close()


if __name__ == "__main__":
    main()
