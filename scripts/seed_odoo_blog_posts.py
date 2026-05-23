#!/usr/bin/env python3
"""Seed a few published Odoo website blog posts for the Chocoloco app.

Loads ODOO_* variables from .env and creates posts in the Odoo blog module.
Defaults to the blog named 'Chocoloco news' when available.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import xmlrpc.client
from dotenv import load_dotenv


@dataclass(frozen=True)
class BlogPostSeed:
    title: str
    content: str


SEEDS = [
    BlogPostSeed(
        title='Nieuw in Chocoloco: seizoenscollectie 2026',
        content=(
            '<p>De nieuwe seizoenscollectie staat nu live in onze webshop.</p>'
            '<p>Met frisse smaken, limited editions en een nieuwe selectie cadeauboxen.</p>'
        ),
    ),
    BlogPostSeed(
        title='Blogupdate: hoe je chocolade langer vers houdt',
        content=(
            '<p>Bewaar chocolade koel, droog en uit direct zonlicht.</p>'
            '<p>Zo blijven textuur en smaak langer optimaal.</p>'
        ),
    ),
    BlogPostSeed(
        title='Aankondiging: nieuwe proefmomenten in de winkel',
        content=(
            '<p>We plannen extra proefmomenten voor nieuwe smaken en combinaties.</p>'
            '<p>Volg de blog voor de exacte data en inschrijving.</p>'
        ),
    ),
]


def load_config() -> tuple[str, str, str, str]:
    load_dotenv()
    odoo_url = os.environ.get('ODOO_URL', '').strip().rstrip('/')
    odoo_db = os.environ.get('ODOO_DB', '').strip()
    odoo_username = os.environ.get('ODOO_USERNAME', '').strip()
    odoo_password = os.environ.get('ODOO_PASSWORD', '').strip()

    if not all([odoo_url, odoo_db, odoo_username, odoo_password]):
        raise SystemExit('Missing ODOO_URL, ODOO_DB, ODOO_USERNAME or ODOO_PASSWORD in .env')

    return odoo_url, odoo_db, odoo_username, odoo_password


def authenticate(odoo_url: str, odoo_db: str, odoo_username: str, odoo_password: str):
    common = xmlrpc.client.ServerProxy(f'{odoo_url}/xmlrpc/2/common')
    uid = common.authenticate(odoo_db, odoo_username, odoo_password, {})
    if not uid:
        raise SystemExit('Odoo authentication failed')
    models = xmlrpc.client.ServerProxy(f'{odoo_url}/xmlrpc/2/object')
    return uid, models


def resolve_blog_id(models, odoo_db: str, uid: int, odoo_password: str) -> int:
    preferred = models.execute_kw(
        odoo_db,
        uid,
        odoo_password,
        'blog.blog',
        'search_read',
        [[('name', '=', 'Chocoloco news')]],
        {'fields': ['id', 'name'], 'limit': 1},
    )
    if preferred:
        return int(preferred[0]['id'])

    fallback = models.execute_kw(
        odoo_db,
        uid,
        odoo_password,
        'blog.blog',
        'search',
        [[]],
        {'limit': 1},
    )
    if not fallback:
        raise SystemExit('No blog.blog records found in Odoo')
    return int(fallback[0])


def existing_titles(models, odoo_db: str, uid: int, odoo_password: str, blog_id: int) -> set[str]:
    posts = models.execute_kw(
        odoo_db,
        uid,
        odoo_password,
        'blog.post',
        'search_read',
        [[('blog_id', '=', blog_id)]],
        {'fields': ['name'], 'limit': 200},
    )
    return {str(post.get('name') or '').strip() for post in posts}


def create_seed_posts(models, odoo_db: str, uid: int, odoo_password: str, blog_id: int) -> list[str]:
    created_titles: list[str] = []
    current_titles = existing_titles(models, odoo_db, uid, odoo_password, blog_id)

    for seed in SEEDS:
        if seed.title in current_titles:
            continue

        vals = {
            'name': seed.title,
            'content': seed.content,
            'blog_id': blog_id,
            'website_published': True,
        }
        post_id = models.execute_kw(
            odoo_db,
            uid,
            odoo_password,
            'blog.post',
            'create',
            [vals],
        )
        created_titles.append(f'{seed.title} (id={post_id})')

    return created_titles


def main() -> None:
    odoo_url, odoo_db, odoo_username, odoo_password = load_config()
    uid, models = authenticate(odoo_url, odoo_db, odoo_username, odoo_password)
    blog_id = resolve_blog_id(models, odoo_db, uid, odoo_password)
    created_titles = create_seed_posts(models, odoo_db, uid, odoo_password, blog_id)

    print(f'Using blog_id={blog_id}')
    if created_titles:
        print('Created posts:')
        for item in created_titles:
            print(f'- {item}')
    else:
        print('No new posts created; all seed titles already existed.')


if __name__ == '__main__':
    main()
