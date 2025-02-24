from flask import Flask, request, jsonify
import requests
import xmltodict
import dateutil.parser
from datetime import datetime, timedelta
import math
from unidecode import unidecode

app = Flask(__name__)

# URL da API XML original
XML_URL = "https://restrito.casteldigital.com.br/vivareal_open/guilhermepilger-vivareal.xml?auth=gVQP3yQzqn"

def normalize_text(text):
    """
    Remove acentos, converte para minúsculas e remove espaços em branco extras.
    """
    if isinstance(text, str):
        return unidecode(text).lower().strip()
    return ""

@app.route('/')
def home():
    return "Middleware de conversão XML para JSON com filtros está rodando!"

@app.route('/convert-xml', methods=['GET'])
def convert_xml():
    response = requests.get(XML_URL)
    if response.status_code == 200:
        data_dict = xmltodict.parse(response.text)
        if "ListingDataFeed" in data_dict and "Listings" in data_dict["ListingDataFeed"]:
            listings = data_dict["ListingDataFeed"]["Listings"]["Listing"]
            # Se houver apenas um imóvel, transforma em lista para evitar erros
            if isinstance(listings, dict):
                listings = [listings]
                
            try:
                # Filtros básicos com normalização
                nome_imovel = normalize_text(request.args.get("nome_imovel", ""))
                cidade = normalize_text(request.args.get("cidade", ""))
                bairro = normalize_text(request.args.get("bairro", ""))
                preco_min = float(request.args.get("preco_min", 0))
                preco_max = float(request.args.get("preco_max", float('inf')))
                tipo_imovel = normalize_text(request.args.get("tipo_imovel", ""))
                finalidade = normalize_text(request.args.get("finalidade", ""))  # venda, aluguel
                
                # Filtros de características
                quartos_min = int(request.args.get("quartos_min", 0))
                suites_min = int(request.args.get("suites_min", 0))
                banheiros_min = int(request.args.get("banheiros_min", 0))
                vagas_min = int(request.args.get("vagas_min", 0))
                
                # Filtros de área
                area_min = float(request.args.get("area_min", 0))
                area_max = float(request.args.get("area_max", float('inf')))
                
                # Filtros de características/desejos
                caracteristicas = normalize_text(request.args.get("caracteristicas", ""))
                
                # Filtros avançados
                palavras_chave = normalize_text(request.args.get("palavras_chave", ""))
                dias_atras = int(request.args.get("dias_atras", 0))
                
                # Filtros de localização por distância
                lat = request.args.get("lat")
                lng = request.args.get("lng")
                raio = float(request.args.get("raio", 5))  # em km
                
                # Opções de ordenação
                ordenar_por = request.args.get("ordenar_por", "")  # preco, area, quartos, data
                ordem = request.args.get("ordem", "asc")  # asc ou desc
                
                # Opções de paginação
                pagina = int(request.args.get("pagina", 1))
                itens_por_pagina = int(request.args.get("itens_por_pagina", 10))
            except ValueError:
                return jsonify({"error": "Parâmetros inválidos. Verifique os valores numéricos."}), 400
            
            listings_filtrados = []
            for listing in listings:
                # Normalizar dados básicos
                title = normalize_text(listing.get("Title", ""))
                details = listing.get("Details", {})
                location = listing.get("Location", {})
                
                # Extração e conversão dos valores numéricos
                try:
                    preco_info = details.get("ListPrice", {}).get("#text", "0")
                    preco = float(preco_info)
                except (ValueError, TypeError):
                    preco = 0
                    
                try:
                    num_quartos = int(details.get("Bedrooms", 0))
                except (ValueError, TypeError):
                    num_quartos = 0
                    
                try:
                    num_suites = int(details.get("Suites", 0))
                except (ValueError, TypeError):
                    num_suites = 0
                    
                try:
                    num_banheiros = int(details.get("Bathrooms", 0))
                except (ValueError, TypeError):
                    num_banheiros = 0
                    
                try:
                    area = float(details.get("LivingArea", {}).get("#text", 0))
                except (ValueError, TypeError):
                    area = 0
                    
                try:
                    vagas = int(details.get("Garage", {}).get("#text", 0))
                except (ValueError, TypeError):
                    vagas = 0
                
                # Dados para filtros avançados
                property_type = normalize_text(details.get("PropertyType", ""))
                tipologia = normalize_text(details.get("Tipologia", ""))
                descricao = normalize_text(details.get("Description", ""))
                transaction_type = normalize_text(listing.get("TransactionType", ""))
                
                # Features/Características
                features = details.get("Features", {}).get("Feature", [])
                if isinstance(features, str):
                    features = [features]
                features_lower = [normalize_text(f) for f in features]
                
                # 1. Filtrar por nome do imóvel
                if nome_imovel and nome_imovel not in title:
                    continue
                
                # 2. Filtrar por cidade
                if cidade and cidade not in normalize_text(location.get("City", "")):
                    continue
                    
                # 3. Filtrar por bairro
                if bairro and bairro not in normalize_text(location.get("Neighborhood", "")):
                    continue
                
                # 4. Filtrar por preço
                if not (preco_min <= preco <= preco_max):
                    continue
                
                # 5. Filtrar por tipo de imóvel
                if tipo_imovel and (tipo_imovel not in tipologia and tipo_imovel not in property_type):
                    continue
                
                # 6. Filtrar por finalidade (venda/aluguel)
                if finalidade:
                    if finalidade == "venda" and "sale" not in transaction_type:
                        continue
                    if finalidade == "aluguel" and "rent" not in transaction_type:
                        continue
                
                # 7. Filtrar por número de quartos
                if num_quartos < quartos_min:
                    continue
                    
                # 8. Filtrar por número de suítes
                if num_suites < suites_min:
                    continue
                    
                # 9. Filtrar por número de banheiros
                if num_banheiros < banheiros_min:
                    continue
                    
                # 10. Filtrar por vagas de garagem
                if vagas < vagas_min:
                    continue
                
                # 11. Filtrar por área
                if not (area_min <= area <= area_max):
                    continue
                
                # 12. Filtrar por características/desejos
                if caracteristicas:
                    lista_caract = [c.strip() for c in caracteristicas.split(",")]
                    if not any(c in features_lower for c in lista_caract):
                        continue
                
                # 13. Filtrar por palavras-chave na descrição ou título
                if palavras_chave:
                    palavras = palavras_chave.split()
                    if not any(p in descricao or p in title for p in palavras):
                        continue
                
                # 14. Filtrar por data de listagem
                if dias_atras > 0:
                    try:
                        data_limite = datetime.now() - timedelta(days=dias_atras)
                        data_listagem = dateutil.parser.parse(listing.get("ListDate", ""))
                        if data_listagem < data_limite:
                            continue
                    except:
                        pass
                
                # 15. Filtrar por distância (se coordenadas forem fornecidas)
                if lat and lng:
                    try:
                        lat1 = float(lat)
                        lng1 = float(lng)
                        lat2 = float(location.get("Latitude", 0))
                        lng2 = float(location.get("Longitude", 0))
                        # Cálculo aproximado da distância em km
                        distancia = math.sqrt((lat2 - lat1)**2 + (lng2 - lng1)**2) * 111
                        if distancia > raio:
                            continue
                    except:
                        pass
                
                # Se chegou até aqui, o imóvel passou em todos os filtros
                listings_filtrados.append(listing)
            
            # Ordenação dos resultados
            if ordenar_por:
                reverse_order = (ordem.lower() == "desc")
                if ordenar_por == "preco":
                    listings_filtrados.sort(
                        key=lambda x: float(x.get("Details", {}).get("ListPrice", {}).get("#text", 0)),
                        reverse=reverse_order
                    )
                elif ordenar_por == "area":
                    listings_filtrados.sort(
                        key=lambda x: float(x.get("Details", {}).get("LivingArea", {}).get("#text", 0)),
                        reverse=reverse_order
                    )
                elif ordenar_por == "quartos":
                    listings_filtrados.sort(
                        key=lambda x: int(x.get("Details", {}).get("Bedrooms", 0)),
                        reverse=reverse_order
                    )
                elif ordenar_por == "data":
                    def get_date(listing):
                        try:
                            return dateutil.parser.parse(listing.get("ListDate", ""))
                        except:
                            return datetime.min
                    listings_filtrados.sort(key=get_date, reverse=reverse_order)
            
            # Aplicar paginação
            total_imoveis = len(listings_filtrados)
            inicio = (pagina - 1) * itens_por_pagina
            fim = inicio + itens_por_pagina
            listings_paginados = listings_filtrados[inicio:fim]
            
            return jsonify({
                "total": total_imoveis,
                "pagina": pagina,
                "itens_por_pagina": itens_por_pagina,
                "total_paginas": (total_imoveis + itens_por_pagina - 1) // itens_por_pagina,
                "Listings": listings_paginados
            })
            
    return jsonify({"error": "Falha ao obter dados da API"}), response.status_code

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000, debug=True)
