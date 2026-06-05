import re

class ClientMappingService:
    """
    Service to classify clients into Business Units based on their names.
    Units: 'Indústria', 'Construção Civil', 'Varejo', or default 'Outros'.
    """
    @staticmethod
    def classify_client(client_name: str) -> str:
        if not client_name:
            return "Outros"
        
        name = client_name.strip()
        
        # Regex definitions
        # Construção Civil: construtoras, engenharia, incorporadoras, obras, civil, forte
        construction_pattern = re.compile(
            r"(constru|construtora|obras|engenharia|incorporadora|civil|forte)", 
            re.IGNORECASE
        )
        
        # Varejo: lojas, supermercados, varejo, comércio, distribuidoras, fashion, têxtil, magazine
        retail_pattern = re.compile(
            r"(varejo|supermercado|loja|distribuidora|comercial|comercio|comércio|têxtil|textil|fashion|magazine|shopping|atacado)", 
            re.IGNORECASE
        )
        
        # Indústria: indústrias, ind, metalúrgica, automotiva, embalagens, corp, biohealth, premium, tecnologia, inovare, eletrônicos, delta
        industry_pattern = re.compile(
            r"(ind|indústria|industria|industrial|metal|automotiva|embalagens|corp|biohealth|premium|tecnologia|inovare|eletrônicos|eletronicos|delta)", 
            re.IGNORECASE
        )
        
        # Priority mapping checks
        if construction_pattern.search(name):
            return "Construção Civil"
        elif retail_pattern.search(name):
            return "Varejo"
        elif industry_pattern.search(name):
            return "Indústria"
        else:
            return "Outros"
