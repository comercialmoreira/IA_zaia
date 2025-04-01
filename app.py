from flask import Flask, request, jsonify
import requests
import xmltodict
import dateutil.parser
from datetime import datetime, timedelta
import math
from unidecode import unidecode
import urllib.parse

app = Flask(__name__)

# URL da API XML original
XML_URL = "https://restrito.casteldigital.com.br/vivareal_open/guilhermepilger-vivareal.xml?auth=gVQP3yQzqn"

def normalize_text(text):
    """
    Remove acentos, converte para minúsculas e remove espaços em branco extras.
    Também lida com dupla codificação de URL.
    """
    if text is None:
        return ""
    try:
        if isinstance(text, str):
            # Tenta decodificar a URL, caso esteja codificada
            text = urllib.parse.unquote(text)
            # Tenta decodificar mais uma vez, caso tenha havido dupla codificação
            if '%' in text:
                text = urllib.parse.unquote(text)
            return unidecode(text).lower().strip()
        return ""
    except:
        return ""

def safe_float(value, default=0.0, min_value=None):
    """
    Converte valor para float com tratamento de erros.
    Garante que o valor não seja menor que min_value (se especificado).
    """
    if value is None:
        return default
    try:
        float_value = float(value)
        if min_value is not None and float_value < min_value:
            return min_value
        return float_value
    except (ValueError, TypeError):
        return default

def safe_int(value, default=0, min_value=None):
    """
    Converte valor para int com tratamento de erros.
    Garante que o valor não seja menor que min_value (se especificado).
    """
    if value is None:
        return default
    try:
        int_value = int(value)
        if min_value is not None and int_value < min_value:
            return min_value
        return int_value
    except (ValueError, TypeError):
        return default

@app.route('/')
def home():
    return "Middleware de conversão XML para JSON com filtros está rodando!"

@app.route('/convert-xml', methods=['GET'])
def convert_xml():
    try:
        response = requests.get(XML_URL)
        if response.status_code != 200:
            return jsonify({"error": f"Falha ao obter dados da API: {response.status_code}"}), response.status_code
            
        try:
            data_dict = xmltodict.parse(response.text)
        except Exception as e:
            return jsonify({"error": f"Erro ao analisar XML: {str(e)}"}), 500
            
        if "ListingDataFeed" not in data_dict or "Listings" not in data_dict["ListingDataFeed"]:
            return jsonify({"error": "Formato de dados inválido"}), 500
            
        listings = data_dict["ListingDataFeed"]["Listings"].get("Listing", [])
        
        # Se houver apenas um imóvel, transforma em lista para evitar erros
        if isinstance(listings, dict):
            listings = [listings]
        
        # Se listings estiver vazio, retorna resposta vazia
        if not listings:
            return jsonify({
                "total": 0,
                "pagina": 1,
                "itens_por_pagina": 10,
                "total_paginas": 0,
                "Listings": []
            })
            
        # Obter e validar parâmetros da requisição
        # Filtros básicos com normalização e valores padrão seguros
        nome_imovel = normalize_text(request.args.get("nome_imovel", ""))
        cidade = normalize_text(request.args.get("cidade", ""))
        bairro = normalize_text(request.args.get("bairro", ""))
        preco_filtro = safe_float(request.args.get("preco"), 0, min_value=0)
        tipo_imovel = normalize_text(request.args.get("tipo_imovel", ""))
        finalidade = normalize_text(request.args.get("finalidade", ""))
        
        # Filtros de características
        quartos_min = safe_int(request.args.get("quartos_min"), 0, min_value=0)
        suites_min = safe_int(request.args.get("suites_min"), 0, min_value=0)
        banheiros_min = safe_int(request.args.get("banheiros_min"), 0, min_value=0)
        vagas_min = safe_int(request.args.get("vagas_min"), 0, min_value=0)
        
        # Filtros de área
        area_min = safe_float(request.args.get("area_min"), 0, min_value=0)
        area_max = safe_float(request.args.get("area_max"), float('inf'), min_value=0)
        
        # Filtros de características/desejos
        caracteristicas = normalize_text(request.args.get("caracteristicas", ""))
        
        # Filtros avançados
        palavras_chave = normalize_text(request.args.get("palavras_chave", ""))
        dias_atras = safe_int(request.args.get("dias_atras"), 0, min_value=0)
        
        # Filtros de localização por distância
        lat = request.args.get("lat")
        lng = request.args.get("lng")
        raio = safe_float(request.args.get("raio"), 5, min_value=0)  # em km
        
        # Opções de ordenação
        ordenar_por = request.args.get("ordenar_por", "")
        ordem = request.args.get("ordem", "asc").lower()
        
        # Opções de paginação
        pagina = safe_int(request.args.get("pagina"), 1, min_value=1)
        itens_por_pagina = safe_int(request.args.get("itens_por_pagina"), 10, min_value=1)
        
        listings_filtrados = []
        for listing in listings:
            # Normalizar dados básicos com proteção contra None
            title = normalize_text(listing.get("Title", ""))
            details = listing.get("Details", {}) or {}
            location = listing.get("Location", {}) or {}
            
            # Extração e conversão dos valores numéricos de forma segura
            # Garante que o preço seja no mínimo 1000
            preco = safe_float(details.get("ListPrice", {}).get("#text") if isinstance(details.get("ListPrice"), dict) else details.get("ListPrice"), min_value=1000)
            num_quartos = safe_int(details.get("Bedrooms"), min_value=0)
            num_suites = safe_int(details.get("Suites"), min_value=0)
            num_banheiros = safe_int(details.get("Bathrooms"), min_value=0)
            area = safe_float(details.get("LivingArea", {}).get("#text") if isinstance(details.get("LivingArea"), dict) else details.get("LivingArea"), min_value=0)
            vagas = safe_int(details.get("Garage", {}).get("#text") if isinstance(details.get("Garage"), dict) else details.get("Garage"), min_value=0)
            
            # Dados para filtros avançados
            property_type = normalize_text(details.get("PropertyType", ""))
            tipologia = normalize_text(details.get("Tipologia", ""))
            descricao = normalize_text(details.get("Description", ""))
            transaction_type = normalize_text(listing.get("TransactionType", ""))
            
            # Features/Características com verificação de tipo
            features = details.get("Features", {})
            if not isinstance(features, dict):
                features = {}
            feature_list = features.get("Feature", [])
            if feature_list is None:
                feature_list = []
            if isinstance(feature_list, str):
                feature_list = [feature_list]
            features_lower = [normalize_text(f) for f in feature_list]
            
            # Aplicando os filtros apenas se os parâmetros não estiverem vazios
            
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
            if preco_filtro > 0 and abs(preco - preco_filtro) > 100:  # Tolerância de 100 unidades
                continue
            
            # 5. Filtrar por tipo de imóvel
            if tipo_imovel and (tipo_imovel not in tipologia and tipo_imovel not in property_type):
                continue
            
            # 6. Filtrar por finalidade (venda/aluguel)
            if finalidade:
                # Melhorar a detecção de finalidade
                if "venda" in finalidade or "compra" in finalidade:
                    if "sale" not in transaction_type and "purchase" not in transaction_type:
                        continue
                elif "aluguel" in finalidade or "locacao" in finalidade or "locação" in finalidade:
                    if "rent" not in transaction_type and "rental" not in transaction_type:
                        continue
                elif "moradia" in finalidade:
                    # Assumir que "moradia" se refere a qualquer tipo de imóvel residencial
                    pass  # Não filtra por finalidade neste caso
            
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
                lista_caract = [c.strip() for c in caracteristicas.split(",") if c.strip()]
                # Se não houver vírgulas, tenta dividir por espaços
                if len(lista_caract) <= 1 and " " in caracteristicas:
                    lista_caract = [c.strip() for c in caracteristicas.split() if c.strip()]
                
                # Primeiro verificamos as características exatas
                features_text = " ".join(features_lower)
                
                # Verifica se alguma das características está presente nas features
                if lista_caract and not any(c in features_text for c in lista_caract):
                    # Se não encontrar nas features, verifica na descrição
                    if not any(c in descricao for c in lista_caract):
                        continue
            
            # 13. Filtrar por palavras-chave na descrição ou título
            if palavras_chave:
                palavras = [p for p in palavras_chave.split() if p]
                if palavras and not any(p in descricao or p in title for p in palavras):
                    continue
            
            # 14. Filtrar por data de listagem
            if dias_atras > 0:
                try:
                    data_limite = datetime.now() - timedelta(days=dias_atras)
                    data_listagem_str = listing.get("ListDate", "")
                    if data_listagem_str:
                        data_listagem = dateutil.parser.parse(data_listagem_str)
                        if data_listagem < data_limite:
                            continue
                except:
                    # Se ocorrer erro na conversão da data, não filtrar por este critério
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
                    # Se ocorrer erro no cálculo da distância, não filtrar por este critério
                    pass
            
            # Se chegou até aqui, o imóvel passou em todos os filtros
            listings_filtrados.append(listing)
        
        # Ordenação dos resultados com tratamento de erros
        if ordenar_por:
            reverse_order = (ordem == "desc")
            try:
                if ordenar_por == "preco":
                    listings_filtrados.sort(
                        key=lambda x: safe_float(
                            x.get("Details", {}).get("ListPrice", {}).get("#text") 
                            if isinstance(x.get("Details", {}).get("ListPrice"), dict) 
                            else x.get("Details", {}).get("ListPrice"),
                            min_value=1000
                        ),
                        reverse=reverse_order
                    )
                elif ordenar_por == "area":
                    listings_filtrados.sort(
                        key=lambda x: safe_float(
                            x.get("Details", {}).get("LivingArea", {}).get("#text")
                            if isinstance(x.get("Details", {}).get("LivingArea"), dict)
                            else x.get("Details", {}).get("LivingArea"),
                            min_value=0
                        ),
                        reverse=reverse_order
                    )
                elif ordenar_por == "quartos":
                    listings_filtrados.sort(
                        key=lambda x: safe_int(x.get("Details", {}).get("Bedrooms"), min_value=0),
                        reverse=reverse_order
                    )
                elif ordenar_por == "data":
                    def get_date(listing):
                        try:
                            data_str = listing.get("ListDate", "")
                            if data_str:
                                return dateutil.parser.parse(data_str)
                            return datetime.min
                        except:
                            return datetime.min
                    listings_filtrados.sort(key=get_date, reverse=reverse_order)
            except Exception as e:
                # Em caso de erro na ordenação, continue sem ordenar
                pass
        
        # Aplicar paginação
        total_imoveis = len(listings_filtrados)
        inicio = (pagina - 1) * itens_por_pagina
        fim = inicio + itens_por_pagina
        listings_paginados = listings_filtrados[inicio:fim] if inicio < total_imoveis else []
        
        return jsonify({
            "total": total_imoveis,
            "pagina": pagina,
            "itens_por_pagina": itens_por_pagina,
            "total_paginas": max(1, (total_imoveis + itens_por_pagina - 1) // itens_por_pagina) if total_imoveis > 0 else 0,
            "Listings": listings_paginados
        })
    
    except Exception as e:
        # Tratamento geral de erros para garantir que a API sempre responda
        return jsonify({
            "error": f"Erro ao processar a requisição: {str(e)}",
            "total": 0,
            "pagina": 1,
            "itens_por_pagina": 10,
            "total_paginas": 0,
            "Listings": []
        }), 500

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000, debug=True)
