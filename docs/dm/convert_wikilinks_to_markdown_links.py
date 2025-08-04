import os
import re

# Caminho da pasta onde estão os .md
folder_path = "."  # ← muda isto para o caminho certo

# Função para transformar o nome do ficheiro num rótulo legível
def humanize_label(filename):
    name = filename.replace(".md", "")
    name = name.replace("_", " ")

    # Capitalizações comuns em português
    name = re.sub(r"\bsessao\b", "Sessão", name, flags=re.IGNORECASE)
    name = re.sub(r"\bresumo\b", "Resumo", name, flags=re.IGNORECASE)
    name = re.sub(r"\bnota\b", "Nota", name, flags=re.IGNORECASE)
    name = re.sub(r"\bsessoes\b", "Sessões", name, flags=re.IGNORECASE)
    name = re.sub(r"\bdm\b", "DM", name, flags=re.IGNORECASE)

    # Capitaliza cada palavra (excepto siglas)
    name = " ".join([word.capitalize() if not word.isupper() else word for word in name.split()])
    return name

# Processa todos os ficheiros .md na pasta
for filename in os.listdir(folder_path):
    if filename.endswith(".md"):
        file_path = os.path.join(folder_path, filename)
        with open(file_path, "r", encoding="utf-8") as file:
            content = file.read()

        # Substitui todos os links: ignora o texto atual e usa o nome do ficheiro
        new_content = re.sub(
            r"\[[^\]]*?\]\(([^)]+\.md)\)",
            lambda match: f"[{humanize_label(os.path.basename(match.group(1)))}]({match.group(1)})",
            content
        )

        # Só escreve se houver mudanças
        if content != new_content:
            with open(file_path, "w", encoding="utf-8") as file:
                file.write(new_content)
            print(f"[✔] Atualizado: {filename}")
        else:
            print(f"[—] Sem alterações: {filename}")
