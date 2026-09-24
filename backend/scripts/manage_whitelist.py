#!/usr/bin/env python3
"""
Operator CLI for Anclora PurgeDoc closed whitelist management.
Commands: add, list, revoke, rotate.
Reuses backend models and security functions.
"""
import sys
import os
import argparse
from pathlib import Path
from datetime import datetime, timezone, timedelta

# Ensure backend directory is in sys.path
backend_dir = Path(__file__).resolve().parents[1]
workspace_dir = Path(__file__).resolve().parents[2]
if str(workspace_dir) not in sys.path:
    sys.path.insert(0, str(workspace_dir))
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from backend.auth.database import SessionLocal
from backend.auth.models import UserRow, AuthWhitelistRow
from backend.auth.security import (
    hash_token,
    generate_raw_token,
    record_audit_event,
    AUTH_WHITELIST_TOKEN_TTL_HOURS
)


def cmd_add(args):
    email = args.email.strip().lower()
    if not email or "@" not in email:
        print("ERROR: Correo electrónico inválido.", file=sys.stderr)
        sys.exit(1)

    admin_email = (args.admin_email or "operator_cli").strip().lower()

    db = SessionLocal()
    try:
        existing = db.query(AuthWhitelistRow).filter(AuthWhitelistRow.email == email).first()
        if existing and existing.status == "active":
            print(f"ERROR: El correo {email} ya cuenta con acceso activo en la whitelist.", file=sys.stderr)
            sys.exit(1)

        raw_token = generate_raw_token()
        t_hash = hash_token(raw_token)
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=AUTH_WHITELIST_TOKEN_TTL_HOURS)

        if existing:
            existing.status = "pending"
            existing.token_hash = t_hash
            existing.expires_at = expires_at
            existing.revoked_at = None
            existing.updated_at = now
            entry = existing
        else:
            entry = AuthWhitelistRow(
                email=email,
                status="pending",
                token_hash=t_hash,
                expires_at=expires_at,
                created_by=admin_email,
                created_at=now,
                updated_at=now
            )
            db.add(entry)

        record_audit_event(
            db, "whitelist_added_cli",
            email=email,
            metadata={"operator": admin_email, "expires_at": expires_at.isoformat()}
        )
        db.commit()
        db.refresh(entry)

        print("-----------------------------------------------------------------")
        print("INVITACIÓN CREADA CORRECTAMENTE (OPERATOR CLI)")
        print("-----------------------------------------------------------------")
        print(f"ID:          {entry.id}")
        print(f"Email:       {entry.email}")
        print(f"Status:      {entry.status}")
        print(f"Expira:      {entry.expires_at.isoformat()}")
        print(f"Token:       {raw_token}")
        print(f"URL:         /activate?token={raw_token}")
        print("-----------------------------------------------------------------")
        print("NOTA: El token se muestra una sola vez. En base de datos sólo")
        print("se almacena su hash SHA-256 no invertible.")
        print("-----------------------------------------------------------------")
    finally:
        db.close()


def cmd_list(args):
    db = SessionLocal()
    try:
        entries = db.query(AuthWhitelistRow).order_by(AuthWhitelistRow.created_at.desc()).all()
        if not entries:
            print("No hay entradas en la whitelist.")
            return

        print(f"{ID:<38} {EMAIL:<32} {STATUS:<10} {EXPIRES_AT:<26} {USER_ID:<38}")
        print("-" * 150)
        for e in entries:
            exp = e.expires_at.isoformat() if e.expires_at else "-"
            uid = e.user_id or "-"
            print(f"{e.id:<38} {e.email:<32} {e.status:<10} {exp:<26} {uid:<38}")
    finally:
        db.close()


def cmd_revoke(args):
    target = args.target.strip()
    db = SessionLocal()
    try:
        entry = db.query(AuthWhitelistRow).filter(
            (AuthWhitelistRow.id == target) | (AuthWhitelistRow.email == target.lower())
        ).first()

        if not entry:
            print(f"ERROR: Entrada {target} no encontrada en la whitelist.", file=sys.stderr)
            sys.exit(1)

        now = datetime.now(timezone.utc)
        entry.status = "revoked"
        entry.token_hash = None
        entry.revoked_at = now
        entry.updated_at = now

        if entry.user_id:
            user = db.query(UserRow).filter(UserRow.id == entry.user_id).first()
            if user:
                user.status = "disabled"

        admin_email = (args.admin_email or "operator_cli").strip().lower()
        record_audit_event(
            db, "whitelist_revoked_cli",
            email=entry.email,
            metadata={"operator": admin_email, "linked_user_id": entry.user_id}
        )
        db.commit()

        print(f"Acceso revocado correctamente para {entry.email} (ID: {entry.id}).")
        if entry.user_id:
            print(f"Cuenta de usuario {entry.user_id} deshabilitada.")
    finally:
        db.close()


def cmd_rotate(args):
    target = args.target.strip()
    db = SessionLocal()
    try:
        entry = db.query(AuthWhitelistRow).filter(
            (AuthWhitelistRow.id == target) | (AuthWhitelistRow.email == target.lower())
        ).first()

        if not entry:
            print(f"ERROR: Entrada {target} no encontrada en la whitelist.", file=sys.stderr)
            sys.exit(1)

        raw_token = generate_raw_token()
        now = datetime.now(timezone.utc)
        entry.token_hash = hash_token(raw_token)
        entry.expires_at = now + timedelta(hours=AUTH_WHITELIST_TOKEN_TTL_HOURS)
        entry.status = "pending"
        entry.updated_at = now

        admin_email = (args.admin_email or "operator_cli").strip().lower()
        record_audit_event(
            db, "whitelist_token_rotated_cli",
            email=entry.email,
            metadata={"operator": admin_email}
        )
        db.commit()
        db.refresh(entry)

        print("-----------------------------------------------------------------")
        print("TOKEN DE INVITACIÓN ROTADO (OPERATOR CLI)")
        print("-----------------------------------------------------------------")
        print(f"ID:          {entry.id}")
        print(f"Email:       {entry.email}")
        print(f"Status:      {entry.status}")
        print(f"Expira:      {entry.expires_at.isoformat()}")
        print(f"Token:       {raw_token}")
        print(f"URL:         /activate?token={raw_token}")
        print("-----------------------------------------------------------------")
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="Operator CLI para la whitelist de Anclora PurgeDoc.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # add
    p_add = subparsers.add_parser("add", help="Añade un email a la whitelist")
    p_add.add_argument("--email", required=True, help="Email a invitar")
    p_add.add_argument("--admin-email", default="operator_cli", help="Email del operador")

    # list
    subparsers.add_parser("list", help="Lista las entradas de la whitelist")

    # revoke
    p_revoke = subparsers.add_parser("revoke", help="Revoca el acceso de una entrada")
    p_revoke.add_argument("--target", required=True, help="ID o email de la entrada")
    p_revoke.add_argument("--admin-email", default="operator_cli", help="Email del operador")

    # rotate
    p_rotate = subparsers.add_parser("rotate", help="Genera un nuevo token para una entrada")
    p_rotate.add_argument("--target", required=True, help="ID o email de la entrada")
    p_rotate.add_argument("--admin-email", default="operator_cli", help="Email del operador")

    args = parser.parse_args()

    if args.command == "add":
        cmd_add(args)
    elif args.command == "list":
        cmd_list(args)
    elif args.command == "revoke":
        cmd_revoke(args)
    elif args.command == "rotate":
        cmd_rotate(args)


if __name__ == "__main__":
    main()
