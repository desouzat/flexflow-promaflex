/**
 * FlexFlow - Sistema de Ajuda Contextual "The Compass"
 * Configuração de ajuda para cada etapa do Kanban
 */

export const HELP_CONFIG = {
    Staging: {
        title: "Mesa de Conferência - Área de Staging",
        description: "Validação e preparação de dados importados antes da confirmação.",
        rules: [
            "Anexos são obrigatórios apenas para Clientes Novos em pedidos Personalizados",
            "Descrição da customização é obrigatória para qualquer pedido Personalizado",
            "Limite de arquivo: 5MB (Otimização de infraestrutura)",
            "Formatos aceitos: PDF, JPG, PNG",
            "Todos os erros devem ser corrigidos antes de confirmar o PO"
        ],
        nextSteps: [
            "Revisar cada item importado",
            "Marcar itens personalizados e clientes novos",
            "Adicionar descrições e anexos conforme necessário",
            "Confirmar PO quando todos os erros forem resolvidos"
        ],
        icon: "📋",
        requiredFields: [
            "Descrição da customização (se Personalizado)",
            "Anexo (se Personalizado + Cliente Novo)"
        ]
    },

    Comercial: {
        title: "Comercial - Aguardando Processamento",
        description: "Pedidos recém-criados aguardando análise inicial.",
        rules: [
            "Pedidos são criados através da importação de planilhas Excel",
            "Verificar se todos os dados obrigatórios estão preenchidos",
            "Pedidos de reposição têm SLA reduzido (50% do tempo normal)",
            "Pedidos de exportação e primeira ordem têm prioridade visual"
        ],
        nextSteps: [
            "Revisar dados do pedido",
            "Mover para PCP quando pronto para análise"
        ],
        icon: "📋"
    },

    PCP: {
        title: "PCP - Planejamento e Controle de Produção",
        description: "Análise técnica e vinculação de custos de material.",
        rules: [
            "OBRIGATÓRIO: Vincular custo de matéria-prima para cada SKU",
            "Utilizar o sistema 'De-Para' (Alias) para mapear SKUs similares",
            "Definir tipo de embalagem: Caixa, Saco, Pallet, Granel, Outro",
            "Registrar impedimentos de produção se houver",
            "Calcular margem de contribuição baseada nos custos"
        ],
        nextSteps: [
            "Acessar a página de Custos para vincular matéria-prima",
            "Preencher metadados de produção",
            "Mover para Produção quando custos estiverem vinculados"
        ],
        icon: "📊",
        requiredFields: [
            "Custo de matéria-prima (custo_mp_kg)",
            "Rendimento (kg por unidade)",
            "Tipo de embalagem"
        ]
    },

    "Produção/Embalagem": {
        title: "Produção/Embalagem - Fabricação e Controle de Qualidade",
        description: "Execução da produção e registro de quantidades.",
        rules: [
            "OBRIGATÓRIO: Registrar quantidade final produzida",
            "Registrar perdas e refugos se houver",
            "Documentar problemas de qualidade",
            "Atualizar status de impedimentos",
            "Validar conformidade com especificações"
        ],
        nextSteps: [
            "Registrar quantidade produzida no sistema",
            "Documentar não-conformidades",
            "Mover para Expedição quando produção estiver completa"
        ],
        icon: "🏭",
        requiredFields: [
            "Quantidade final produzida",
            "Status de qualidade"
        ]
    },

    "Expedição/Faturamento": {
        title: "Expedição/Faturamento - Preparação e Envio",
        description: "Embalagem final e preparação para envio ao cliente.",
        rules: [
            "Verificar tipo de embalagem definido no PCP",
            "Confirmar endereço de entrega",
            "Gerar documentação de transporte",
            "Registrar data e hora de saída",
            "Atualizar tracking de entrega"
        ],
        nextSteps: [
            "Embalar conforme especificações",
            "Gerar nota fiscal e documentos",
            "Mover para Concluído quando enviado"
        ],
        icon: "📦",
        requiredFields: [
            "Data de envio",
            "Transportadora",
            "Código de rastreamento"
        ]
    },

    Concluído: {
        title: "Concluído - Pedido Finalizado",
        description: "Pedido entregue e finalizado com sucesso.",
        rules: [
            "Pedido foi entregue ao cliente",
            "Todos os documentos foram gerados",
            "Métricas de performance foram registradas",
            "Feedback do cliente pode ser coletado"
        ],
        nextSteps: [
            "Arquivar documentação",
            "Analisar métricas de performance",
            "Coletar feedback do cliente"
        ],
        icon: "✅"
    }
};

/**
 * Obtém a configuração de ajuda para um status específico
 * @param {string} status - Nome do status (ex: "PCP", "Produção")
 * @returns {object} Configuração de ajuda
 */
export function getHelpForStatus(status) {
    return HELP_CONFIG[status] || {
        title: status,
        description: "Informações de ajuda não disponíveis para este status.",
        rules: [],
        nextSteps: [],
        icon: "❓"
    };
}

/**
 * Indicadores estratégicos para pedidos
 */
export const STRATEGIC_INDICATORS = {
    is_export: {
        label: "Exportação",
        icon: "🌍",
        color: "blue",
        tooltip: "Pedido de exportação - Atenção especial para documentação e prazos alfandegários"
    },
    is_first_order: {
        label: "Primeira Ordem",
        icon: "⭐",
        color: "yellow",
        tooltip: "Primeira ordem do cliente - Prioridade para garantir qualidade e impressão positiva"
    },
    is_replacement: {
        label: "Reposição",
        icon: "🔄",
        color: "green",
        tooltip: "Pedido de reposição - SLA reduzido (50% do tempo normal)"
    },
    is_urgent: {
        label: "Urgente",
        icon: "⚡",
        color: "red",
        tooltip: "Pedido urgente - Prioridade máxima"
    }
};

/**
 * Tipos de embalagem disponíveis
 */
export const PACKAGING_TYPES = {
    CAIXA: { label: "Caixa", icon: "📦" },
    SACO: { label: "Saco", icon: "🛍️" },
    PALLET: { label: "Pallet", icon: "🏗️" },
    GRANEL: { label: "Granel", icon: "🌾" },
    OUTRO: { label: "Outro", icon: "📋" }
};

/**
 * Impedimentos de produção estruturados
 */
export const PRODUCTION_IMPEDIMENTS = {
    FALTA_MATERIA_PRIMA: {
        label: "Falta de Matéria-Prima",
        icon: "🔴",
        severity: "high"
    },
    FALTA_INSUMO: {
        label: "Falta de Insumo",
        icon: "🟡",
        severity: "medium"
    },
    EQUIPAMENTO_QUEBRADO: {
        label: "Equipamento Quebrado",
        icon: "🔧",
        severity: "high"
    },
    FALTA_MO: {
        label: "Falta de Mão de Obra",
        icon: "👷",
        severity: "medium"
    },
    PROBLEMA_QUALIDADE: {
        label: "Problema de Qualidade",
        icon: "⚠️",
        severity: "high"
    },
    AGUARDANDO_APROVACAO: {
        label: "Aguardando Aprovação",
        icon: "⏳",
        severity: "low"
    },
    OUTRO: {
        label: "Outro",
        icon: "❓",
        severity: "low"
    }
};
