from __future__ import annotations

import os
import re
from functools import wraps
from typing import Dict, List, Optional

import pandas as pd
from flask import Flask, flash, redirect, render_template, request, session, url_for, jsonify
from sqlalchemy import Boolean, Integer, Numeric, String, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session

APP_NAME = "Carta Vini DolceSalato"

ADMIN_USER = os.environ.get("CARTA_VINI_ADMIN_USER", "admin")
ADMIN_PASS = os.environ.get("CARTA_VINI_ADMIN_PASS", "cambiamipassword")

SHEETS_CSV_URL = os.environ.get("SHEETS_CSV_URL", "").strip()
SHEETS_WEB_URL = os.environ.get("SHEETS_WEB_URL", "").strip()

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()

PREFERRED_CATEGORIES = [
    "I Nostri Calici",
    "Bianchi Piccolini",
    "Rossi Piccolini",
]

def _normalize_pg_url(url: str) -> str:
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg2://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return url

def _db_url() -> str:
    if DATABASE_URL:
        return _normalize_pg_url(DATABASE_URL)
    os.makedirs("data", exist_ok=True)
    return "sqlite:///data/app.db"

engine = create_engine(_db_url(), pool_pre_ping=True)

class Base(DeclarativeBase):
    pass

class Wine(Base):
    __tablename__ = "wines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    categoria: Mapped[str] = mapped_column(String(200), default="", index=True)
    nome_vino: Mapped[str] = mapped_column(String(255), default="", index=True)
    produttore: Mapped[str] = mapped_column(String(255), default="", index=True)
    annata: Mapped[str] = mapped_column(String(50), default="")
    colore: Mapped[str] = mapped_column(String(100), default="", index=True)
    tipologia: Mapped[str] = mapped_column(String(120), default="", index=True)
    denom: Mapped[str] = mapped_column(String(120), default="")
    regione_area: Mapped[str] = mapped_column(String(200), default="", index=True)
    prezzo_eur: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    attivo: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

Base.metadata.create_all(engine)

def create_app() -> Flask:
    app = Flask(__name__)
    app.secret_key = os.environ.get("FLASK_SECRET_KEY", "cambia-questa-chiave-lunga")

    def admin_required(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not session.get("is_admin"):
                return redirect(url_for("login", next=request.path))
            return fn(*args, **kwargs)
        return wrapper

    def norm_cat(s: str) -> str:
        s = (s or "").strip().lower()
        s = re.sub(r"[^a-z0-9\s]", " ", s, flags=re.IGNORECASE)
        s = re.sub(r"\s+", " ", s).strip()
        return s

    def ordered_categories(cats: List[str]) -> List[str]:
        preferred_norm = [norm_cat(x) for x in PREFERRED_CATEGORIES]
        cat_map = {norm_cat(c): c for c in cats}

        ordered: List[str] = []
        for n in preferred_norm:
            if n in cat_map:
                ordered.append(cat_map[n])
                continue
            found = None
            for k, original in cat_map.items():
                if n and (n in k or k in n):
                    found = original
                    break
            if found and found not in ordered:
                ordered.append(found)

        remaining = sorted([c for c in cats if c not in ordered], key=lambda x: norm_cat(x))
        ordered.extend(remaining)
        return ordered

    def group_by_categoria(rows: List[Wine]) -> Dict[str, List[Wine]]:
        groups: Dict[str, List[Wine]] = {}
        for w in rows:
            cat = w.categoria.strip() if w.categoria else "Senza categoria"
            groups.setdefault(cat, []).append(w)

        cats = ordered_categories(list(groups.keys()))
        return {c: groups[c] for c in cats}

    @app.get("/")
    def index():
        with Session(engine) as db:
            wines = db.scalars(select(Wine).where(Wine.attivo == True)).all()

        options = {
            "colore": sorted({w.colore for w in wines if w.colore}, key=lambda x: x.lower()),
            "tipologia": sorted({w.tipologia for w in wines if w.tipologia}, key=lambda x: x.lower()),
            "regione": sorted({w.regione_area for w in wines if w.regione_area}, key=lambda x: x.lower()),
        }
        categorie = group_by_categoria(wines)
        return render_template("index.html", app_name=APP_NAME, categorie=categorie, options=options)

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            user = (request.form.get("username") or "").strip()
            pw = request.form.get("password") or ""
            if user == ADMIN_USER and pw == ADMIN_PASS:
                session["is_admin"] = True
                flash("Accesso effettuato.", "success")
                nxt = request.args.get("next") or url_for("admin")
                return redirect(nxt)
            flash("Credenziali non valide.", "danger")
        return render_template("login.html", app_name=APP_NAME)

    @app.get("/logout")
    def logout():
        session.clear()
        flash("Sei uscito.", "info")
        return redirect(url_for("index"))

    @app.get("/admin")
    @admin_required
    def admin():
        q = (request.args.get("q") or "").strip().lower()
        with Session(engine) as db:
            wines = db.scalars(select(Wine)).all()
        if q:
            wines = [
                w for w in wines
                if q in (w.nome_vino or "").lower()
                or q in (w.produttore or "").lower()
                or q in (w.categoria or "").lower()
                or q in (w.colore or "").lower()
                or q in (w.tipologia or "").lower()
                or q in (w.regione_area or "").lower()
            ]
        wines.sort(key=lambda w: (not w.attivo, (w.categoria or ""), (w.nome_vino or ""), (w.produttore or "")))
        return render_template(
            "admin.html",
            app_name=APP_NAME,
            vini=wines,
            has_sheets=bool(SHEETS_CSV_URL),
            sheets_web_url=SHEETS_WEB_URL,
            q=request.args.get("q", ""),
        )

    @app.post("/admin/toggle/<int:wine_id>")
    @admin_required
    def admin_toggle(wine_id: int):
        attivo = (request.form.get("attivo") or "").strip().lower() in ("1", "true", "on", "yes", "si", "sì")
        with Session(engine) as db:
            w = db.get(Wine, wine_id)
            if not w:
                return jsonify({"ok": False, "error": "not_found"}), 404
            w.attivo = attivo
            db.commit()
        return jsonify({"ok": True, "attivo": attivo})

    @app.post("/admin/add")
    @admin_required
    def admin_add():
        def g(name: str) -> str:
            return (request.form.get(name) or "").strip()

        prezzo_raw = (request.form.get("prezzo_eur") or "").strip()
        prezzo = None
        if prezzo_raw:
            try:
                prezzo = float(prezzo_raw.replace(",", "."))
            except ValueError:
                flash("Prezzo non valido.", "danger")
                return redirect(url_for("admin"))

        w = Wine(
            categoria=g("categoria"),
            nome_vino=g("nome_vino"),
            produttore=g("produttore"),
            annata=g("annata"),
            colore=g("colore"),
            tipologia=g("tipologia"),
            denom=g("denom"),
            regione_area=g("regione_area"),
            prezzo_eur=prezzo,
            attivo=True,
        )
        if not w.nome_vino:
            flash("Nome vino obbligatorio.", "danger")
            return redirect(url_for("admin"))

        with Session(engine) as db:
            db.add(w)
            db.commit()

        flash("Vino aggiunto.", "success")
        return redirect(url_for("admin"))

    @app.post("/admin/delete/<int:wine_id>")
    @admin_required
    def admin_delete(wine_id: int):
        with Session(engine) as db:
            w = db.get(Wine, wine_id)
            if w:
                db.delete(w)
                db.commit()
        flash("Vino eliminato.", "info")
        return redirect(url_for("admin"))

    def _norm_col(col: str) -> str:
        col = (col or "").strip().lower()
        col = col.replace("/", " ")
        col = re.sub(r"[^a-z0-9\s]", " ", col)
        col = re.sub(r"\s+", " ", col).strip()
        return col

    @app.post("/admin/import_from_sheets")
    @admin_required
    def import_from_sheets():
        if not SHEETS_CSV_URL:
            flash("SHEETS_CSV_URL non impostata.", "danger")
            return redirect(url_for("admin"))

        try:
            df = pd.read_csv(SHEETS_CSV_URL)
        except Exception as e:
            flash(f"Errore lettura Google Sheet: {e}", "danger")
            return redirect(url_for("admin"))

        want = {
            "categoria": ["categoria", "category"],
            "nome_vino": ["nome vino", "nome_vino", "vino", "wine name", "nome"],
            "produttore": ["produttore", "producer", "cantina"],
            "annata": ["annata", "anno", "vintage"],
            "colore": ["colore", "color"],
            "tipologia": ["tipologia", "tipo", "type"],
            "denom": ["denom", "denominazione", "doc", "docg", "igt"],
            "regione_area": ["regione area", "regione", "area", "regione/area", "region"],
            "prezzo_eur": ["prezzo eur", "prezzo", "price", "eur"],
            "attivo": ["attivo", "attiva", "active", "visibile", "online"],
        }

        cols_norm = {_norm_col(c): c for c in df.columns}
        rename: dict[str, str] = {}

        for target, aliases in want.items():
            found = None
            for a in aliases:
                a_norm = _norm_col(a)
                if a_norm in cols_norm:
                    found = cols_norm[a_norm]
                    break
                for k_norm, original in cols_norm.items():
                    if a_norm and (a_norm in k_norm or k_norm in a_norm):
                        found = original
                        break
                if found:
                    break
            if found:
                rename[found] = target

        df = df.rename(columns=rename)

        required = ["categoria","nome_vino","produttore","annata","colore","tipologia","denom","regione_area","prezzo_eur","attivo"]
        missing = [c for c in required if c not in df.columns]
        if missing:
            flash("Colonne mancanti nel foglio: " + ", ".join(missing), "danger")
            return redirect(url_for("admin"))

        df["prezzo_eur"] = pd.to_numeric(df["prezzo_eur"], errors="coerce")
        df["attivo"] = df["attivo"].astype(str).str.strip().str.upper().isin(["TRUE","1","YES","Y","SI","SÌ","ON"])

        rows: list[Wine] = []
        for _, r in df.iterrows():
            nome = "" if pd.isna(r["nome_vino"]) else str(r["nome_vino"]).strip()
            if not nome:
                continue
            rows.append(
                Wine(
                    categoria=str(r["categoria"]).strip() if not pd.isna(r["categoria"]) else "",
                    nome_vino=nome,
                    produttore=str(r["produttore"]).strip() if not pd.isna(r["produttore"]) else "",
                    annata=str(r["annata"]).replace(".0", "").strip() if not pd.isna(r["annata"]) else "",
                    colore=str(r["colore"]).strip() if not pd.isna(r["colore"]) else "",
                    tipologia=str(r["tipologia"]).strip() if not pd.isna(r["tipologia"]) else "",
                    denom=str(r["denom"]).strip() if not pd.isna(r["denom"]) else "",
                    regione_area=str(r["regione_area"]).strip() if not pd.isna(r["regione_area"]) else "",
                    prezzo_eur=None if pd.isna(r["prezzo_eur"]) else float(r["prezzo_eur"]),
                    attivo=bool(r["attivo"]),
                )
            )

        with Session(engine) as db:
            db.query(Wine).delete()
            db.add_all(rows)
            db.commit()

        flash(f"Import completato: {len(rows)} vini.", "success")
        return redirect(url_for("admin"))

    return app

app = create_app()
