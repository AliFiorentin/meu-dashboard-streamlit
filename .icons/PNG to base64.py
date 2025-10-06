

from __future__ import annotations
import argparse
import base64
import os
import sys
from pathlib import Path
from typing import Iterable, Tuple

PNG_EXTS = {".png", ".PNG"}

def to_base64(png_path: Path) -> str:
    with png_path.open("rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")

def to_datauri_from_b64(b64: str) -> str:
    return f"data:image/png;base64,{b64}"

def should_convert(src: Path, dst: Path, force: bool) -> bool:
    if force:
        return True
    return not dst.exists() or dst.stat().st_size == 0 or dst.stat().st_mtime < src.stat().st_mtime

def find_pngs(root: Path, recursive: bool) -> Iterable[Path]:
    if recursive:
        yield from (p for p in root.rglob("*") if p.suffix in PNG_EXTS and p.is_file())
    else:
        yield from (p for p in root.glob("*") if p.suffix in PNG_EXTS and p.is_file())

def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        f.write(text)

def convert_one(png_path: Path, write_datauri: bool, write_b64: bool, force: bool) -> Tuple[bool, str]:
    try:
        b64 = to_base64(png_path)
        created_any = False
        msgs = []

        if write_datauri:
            datauri_path = png_path.with_suffix(png_path.suffix + ".datauri")  # ex: "Empresas.png.datauri"
            if should_convert(png_path, datauri_path, force):
                write_text(datauri_path, to_datauri_from_b64(b64))
                created_any = True
                msgs.append(f"→ .datauri: {datauri_path.name}")
            else:
                msgs.append(f"(skip .datauri existe): {datauri_path.name}")

        if write_b64:
            b64_path = png_path.with_suffix(png_path.suffix + ".b64")
            if should_convert(png_path, b64_path, force):
                write_text(b64_path, b64)
                created_any = True
                msgs.append(f"→ .b64: {b64_path.name}")
            else:
                msgs.append(f"(skip .b64 existe): {b64_path.name}")

        return created_any, " | ".join(msgs)
    except Exception as e:
        return False, f"ERRO em {png_path.name}: {e}"

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Converte PNGs em .datauri (e opcionalmente .b64) para uso no Folium/Streamlit.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "-i", "--input-dir", default=".icons", help="Diretório onde estão os PNGs"
    )
    parser.add_argument(
        "-r", "--recursive", action="store_true", help="Varrer subpastas recursivamente"
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--datauri-only", action="store_true", help="Gerar apenas .datauri"
    )
    group.add_argument(
        "--b64-only", action="store_true", help="Gerar apenas .b64"
    )
    parser.add_argument(
        "-f", "--force", action="store_true", help="Sobrescrever arquivos existentes"
    )
    parser.add_argument(
        "-q", "--quiet", action="store_true", help="Saída mínima"
    )

    args = parser.parse_args(argv)

    root = Path(args.input_dir).resolve()
    if not root.exists() or not root.is_dir():
        print(f"Diretório não encontrado: {root}", file=sys.stderr)
        return 2

    write_datauri = True
    write_b64 = False
    if args.datauri_only:
        write_datauri, write_b64 = True, False
    elif args.b64_only:
        write_datauri, write_b64 = False, True

    pngs = list(find_pngs(root, args.recursive))
    if not pngs:
        print(f"Nenhum PNG encontrado em: {root}")
        return 0

    total = len(pngs)
    created = 0
    skipped = 0
    errors = 0

    if not args.quiet:
        print(f"Processando {total} PNG(s) em {root} (recursive={args.recursive})")
        print(f"Geração: .datauri={write_datauri}, .b64={write_b64}, force={args.force}\n")

    for i, p in enumerate(pngs, 1):
        ok, msg = convert_one(p, write_datauri, write_b64, args.force)
        if ok:
            created += 1
            if not args.quiet:
                print(f"[{i}/{total}] {p.name} | {msg}")
        else:
            # msg traz se foi skip ou erro
            if "ERRO" in msg:
                errors += 1
                print(f"[{i}/{total}] {msg}", file=sys.stderr)
            else:
                skipped += 1
                if not args.quiet:
                    print(f"[{i}/{total}] {p.name} | {msg}")

    if not args.quiet:
        print("\nResumo:")
        print(f"  PNGs encontrados : {total}")
        print(f"  Arquivos gerados : {created}")
        print(f"  Ignorados/skip   : {skipped}")
        print(f"  Erros            : {errors}")

    return 0 if errors == 0 else 1

if __name__ == "__main__":
    raise SystemExit(main())
