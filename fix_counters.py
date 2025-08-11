# scripts/fix_counters.py
# Uso:
#   python scripts/fix_counters.py --email usuario@dominio
#   python scripts/fix_counters.py --all   (si tenés una forma de listar usuarios)

import argparse
import storage

def recalcular_para_email(email: str):
    # Lee ideas reales del JSON del usuario
    ideas = storage.cargar_ideas_usuario(email) or []
    total_ideas_reales = len(ideas)

    # Cuenta artículos reales (tu storage ya tiene esta función)
    total_articulos_reales = storage.contar_articulos_usuario(email)

    # Setea contadores históricos exactamente a esos valores
    storage.set_ideas_generadas(email, total_ideas_reales)
    storage.set_articulos_generados(email, total_articulos_reales)

    print(f"[OK] {email}: ideas={total_ideas_reales} artículos={total_articulos_reales}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--email", help="Email del usuario a recalcular")
    ap.add_argument("--all", action="store_true", help="Recalcular para todos los usuarios (si podés listarlos)")
    args = ap.parse_args()

    if args.email:
        recalcular_para_email(args.email)
    elif args.all:
        # Si tenés una forma de listar usuarios, llamala aquí. Ejemplo:
        # for email in storage.listar_emails_usuarios():
        #     recalcular_para_email(email)
        print("Implementá un listado de usuarios o usá --email.")
    else:
        print("Usá --email usuario@dominio o --all.")

if __name__ == "__main__":
    main()