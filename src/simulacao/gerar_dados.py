"""
Gerador do dataset simulado: Raio-X da Frota (Challenge Sem Parar, Sprint 1).

Cria duas frotas fictícias:
  E01 - TransNorte Cargas: dados COMPLETOS, com ineficiências plantadas de propósito.
  E02 - Rota Leve Distribuidora: dados PARCIAIS (só combustível e IPVA),
        para mostrar a estimativa com dados incompletos.

Todos os valores são SIMULADOS. Empresas, placas e fornecedores são fictícios.

Uso:
    python gerar_dados.py      # grava os CSVs em ../../data
"""
from pathlib import Path
import numpy as np
import pandas as pd

rng = np.random.default_rng(42)  # semente fixa: o resultado é sempre o mesmo
OUT = Path(__file__).resolve().parents[2] / "data"
MESES = pd.period_range("2026-04", "2026-09", freq="M")

# Valores de referência (premissas do grupo; trocar por ANP/FIPE na Sprint 2)
PRECO_REF = {"gasolina": 6.30, "diesel": 6.10}            # R$ por litro
KML_REF = {"leve": 11.0, "utilitario": 9.5, "caminhao": 5.0, "carreta": 2.6}
MANUT_RKM = {"leve": 0.12, "utilitario": 0.18, "caminhao": 0.35, "carreta": 0.55}
PEDAGIO_RKM = {"leve": 0.00, "utilitario": 0.03, "caminhao": 0.09, "carreta": 0.16}
VALOR_VEICULO = {"leve": 55_000, "utilitario": 100_000, "caminhao": 250_000, "carreta": 450_000}
IPVA = {"leve": 0.04, "utilitario": 0.04, "caminhao": 0.015, "carreta": 0.015}

EMPRESAS = [
    dict(empresa_id="E01", nome="TransNorte Cargas (fictícia)", segmento="Transporte de cargas",
         uf="PR", dados="completos"),
    dict(empresa_id="E02", nome="Rota Leve Distribuidora (fictícia)", segmento="Distribuição urbana",
         uf="SP", dados="parciais"),
]
# (tipo, quantidade, combustível, km por mês)
FROTA = {
    "E01": [("caminhao", 3, "diesel", 7_500), ("carreta", 5, "diesel", 11_000)],
    "E02": [("leve", 8, "gasolina", 2_500), ("utilitario", 4, "diesel", 3_000)],
}

# Ineficiências plantadas (só na E01, que tem dados completos)
CONSUMO_RUIM = {"E01-V06": 0.82}              # carreta consumindo 18% a mais
POSTO_CARO = ("Posto Estrela (fictício)", 1.09)  # 9% acima da referência
MULTAS_RECORRENTES = {"E01-V02"}
PEDAGIO_SEM_TAG = {"E01-V07", "E01-V08"}


def placa():
    L = list("ABCDEFGHJKLMNPRSTUVWXYZ")
    return f"{''.join(rng.choice(L, 3))}{rng.integers(0, 10)}{rng.choice(L)}{rng.integers(10, 100)}"


def lanc(**k):
    return k


def gerar():
    OUT.mkdir(parents=True, exist_ok=True)

    veiculos = []
    for emp, grupos in FROTA.items():
        n = 0
        for tipo, qtd, comb, km in grupos:
            for _ in range(qtd):
                n += 1
                veiculos.append(dict(veiculo_id=f"{emp}-V{n:02d}", empresa_id=emp, placa=placa(),
                                     tipo=tipo, combustivel=comb,
                                     ano=int(rng.integers(2017, 2025)),
                                     km_mes=int(km * rng.uniform(0.9, 1.1))))
    veiculos = pd.DataFrame(veiculos)

    desp = []
    for v in veiculos.itertuples():
        completo = v.empresa_id == "E01"
        fator = CONSUMO_RUIM.get(v.veiculo_id, rng.uniform(0.96, 1.04))
        for mes in MESES:
            km = int(v.km_mes * rng.uniform(0.9, 1.1))
            litros = km / (KML_REF[v.tipo] * fator)

            # Combustível: um lançamento consolidado por mês e posto
            for parte in (0.5, 0.5):
                posto, mult = "Posto Rede Comum (fictício)", rng.uniform(0.98, 1.02)
                if completo and rng.random() < 0.6:
                    posto, mult = POSTO_CARO
                preco = round(PRECO_REF[v.combustivel] * mult, 2)
                lt = round(litros * parte, 1)
                desp.append(lanc(data=f"{mes}-15", empresa_id=v.empresa_id, veiculo_id=v.veiculo_id,
                                 categoria="combustivel", detalhe=v.combustivel, fornecedor=posto,
                                 valor_rs=round(lt * preco, 2), litros=lt, preco_litro=preco,
                                 km=round(km * parte), origem="planilha"))
            if not completo:
                continue

            # Manutenção: corretiva pesa ~70% (referência: até 30%)
            base = km * MANUT_RKM[v.tipo] * rng.uniform(0.9, 1.1)
            corr = rng.uniform(0.62, 0.78)
            desp.append(lanc(data=f"{mes}-10", empresa_id=v.empresa_id, veiculo_id=v.veiculo_id,
                             categoria="manutencao", detalhe="preventiva", fornecedor="Oficina (fictícia)",
                             valor_rs=round(base * (1 - corr), 2), origem="pdf"))
            desp.append(lanc(data=f"{mes}-20", empresa_id=v.empresa_id, veiculo_id=v.veiculo_id,
                             categoria="manutencao", detalhe="corretiva", fornecedor="Oficina (fictícia)",
                             valor_rs=round(base * corr * 1.3, 2), origem="imagem"))

            # Pedágio
            meio = "manual" if v.veiculo_id in PEDAGIO_SEM_TAG else "tag"
            desp.append(lanc(data=f"{mes}-28", empresa_id=v.empresa_id, veiculo_id=v.veiculo_id,
                             categoria="pedagio", detalhe=meio, fornecedor="Concessionárias",
                             valor_rs=round(km * PEDAGIO_RKM[v.tipo] * rng.uniform(0.9, 1.1), 2),
                             origem="extrato" if meio == "tag" else "imagem"))

            # Multas
            if rng.random() < (0.6 if v.veiculo_id in MULTAS_RECORRENTES else 0.05):
                desp.append(lanc(data=f"{mes}-05", empresa_id=v.empresa_id, veiculo_id=v.veiculo_id,
                                 categoria="multa", detalhe="excesso de velocidade",
                                 fornecedor="Órgão de trânsito", valor_rs=130.16, origem="imagem"))

        # Impostos (todas as empresas) e seguro (só quem tem dados completos), anuais
        valor = VALOR_VEICULO[v.tipo] * 0.93 ** (2026 - v.ano)
        desp.append(lanc(data="2026-04-15", empresa_id=v.empresa_id, veiculo_id=v.veiculo_id,
                         categoria="imposto", detalhe="IPVA + licenciamento", fornecedor="SEFAZ/DETRAN",
                         valor_rs=round(valor * IPVA[v.tipo] + 160, 2), origem="pdf"))
        if completo:
            desp.append(lanc(data="2026-04-20", empresa_id=v.empresa_id, veiculo_id=v.veiculo_id,
                             categoria="seguro", detalhe="apólice anual", fornecedor="Seguradora (fictícia)",
                             valor_rs=round(valor * 0.05, 2), origem="pdf"))

    despesas = pd.DataFrame(desp).sort_values(["empresa_id", "data", "veiculo_id"]).reset_index(drop=True)
    despesas.insert(0, "id", range(1, len(despesas) + 1))
    despesas = despesas[["id", "data", "empresa_id", "veiculo_id", "categoria", "detalhe", "fornecedor",
                         "valor_rs", "litros", "preco_litro", "km", "origem"]]

    ref = [dict(indicador="consumo_km_l", tipo=t, referencia=v) for t, v in KML_REF.items()]
    ref += [dict(indicador="manutencao_r$_por_km", tipo=t, referencia=v) for t, v in MANUT_RKM.items()]
    ref += [dict(indicador="pedagio_r$_por_km", tipo=t, referencia=v) for t, v in PEDAGIO_RKM.items()]
    ref += [dict(indicador=f"preco_litro_{c}", tipo="todos", referencia=p) for c, p in PRECO_REF.items()]
    ref += [dict(indicador="corretiva_max_%", tipo="todos", referencia=30),
            dict(indicador="multas_por_veiculo_mes_max", tipo="todos", referencia=0.1),
            dict(indicador="pedagio_com_tag_%", tipo="todos", referencia=100)]
    referencias = pd.DataFrame(ref)

    pd.DataFrame(EMPRESAS).to_csv(OUT / "empresas.csv", index=False)
    veiculos.to_csv(OUT / "veiculos.csv", index=False)
    despesas.to_csv(OUT / "despesas.csv", index=False)
    referencias.to_csv(OUT / "referencias.csv", index=False)
    return veiculos, despesas, referencias


if __name__ == "__main__":
    v, d, r = gerar()
    print(f"veiculos={len(v)} despesas={len(d)} referencias={len(r)}")
