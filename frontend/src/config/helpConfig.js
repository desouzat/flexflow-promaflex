/**
 * FlexFlow - Sistema de Ajuda Contextual "The Compass"
 * Configuração de ajuda para cada etapa do Kanban
 */

export const HELP_CONFIG = {
    Staging: {
        title: "Mesa de Conferência - Área de Staging",
        description: "Validação e preparação de dados importados antes da confirmação.",
        rules: [
            "✅ REGRA 100% CHECADO: Todos os itens devem estar marcados como 'Checado' antes de confirmar o PO",
            "📎 ANEXOS OBRIGATÓRIOS: Apenas para Clientes Novos em pedidos Personalizados",
            "📝 DESCRIÇÃO OBRIGATÓRIA: Qualquer pedido Personalizado deve ter descrição da customização",
            "📊 MOTOR DE MARGEM DINÂMICA: Margem calculada em tempo real com base no Valor Presente (VP) ajustado a 2.5% a.m. pro-rata e taxa de impostos a 22.25%",
            "🎨 CLASSIFICAÇÃO DE MARGEM: Verde (>= 30%), Amarelo (< 30%), Laranja (< 19%), Vermelho (< 10% ou negativa)",
            "⚙️ STATUS PENDENTE PCP: Exibido em cinza se o custo for zero ou indefinido, garantindo proteção contra Divisão por Zero",
            "⚠️ PAINEL DE RISCO: Sistema exibe alertas visuais para itens que precisam de atenção",
            "📦 LIMITE DE ARQUIVO: 5MB por arquivo (Otimização de infraestrutura)",
            "📄 FORMATOS ACEITOS: PDF, JPG, PNG",
            "🔒 BLOQUEIO DE CONFIRMAÇÃO: Não é possível confirmar PO com erros pendentes ou itens não checados"
        ],
        nextSteps: [
            "Revisar cada item importado no painel de staging",
            "Marcar itens personalizados e clientes novos conforme necessário",
            "Adicionar descrições de customização para itens personalizados",
            "Fazer upload de anexos para clientes novos com itens personalizados (máx 5MB)",
            "Marcar todos os itens como 'Checado' após validação",
            "Verificar o Painel de Risco - todos os alertas devem estar resolvidos",
            "Confirmar PO quando 100% dos itens estiverem checados e sem erros"
        ],
        icon: "📋",
        requiredFields: [
            "Descrição da customização (se Personalizado)",
            "Anexo (se Personalizado + Cliente Novo)",
            "Todos os itens marcados como 'Checado' (100%)"
        ],
        criticalRules: [
            "🚫 REGRA 100%: Impossível confirmar sem todos os itens checados",
            "⚠️ PAINEL DE RISCO: Monitora erros em tempo real",
            "📦 LIMITE 5MB: Arquivos maiores serão rejeitados"
        ]
    },

    Comercial: {
        title: "Comercial - Validação e Processamento Inicial",
        description: "Pedidos aguardando análise comercial. Inclui pedidos SUBMITTED e aqueles aguardando decisão de partição (WAITING_COMMERCIAL_PARTITION).",
        rules: [
            "📊 IMPORTAÇÃO: A planilha Excel deve conter exatamente 19 campos obrigatórios (PO Number, Customer, SKU, Quantity, Unit Price, Delivery Date, etc.)",
            "📝 NOTAS OBRIGATÓRIAS: Itens personalizados DEVEM ter descrição da customização preenchida",
            "🌍 FLAG EXPORTAÇÃO: Pedidos de exportação são marcados automaticamente e têm prioridade visual no Kanban",
            "⭐ FLAG PRIMEIRA ORDEM: Primeira ordem do cliente recebe atenção especial para garantir qualidade",
            "🔄 FLAG REPOSIÇÃO: Pedidos de reposição têm SLA reduzido em 50% (Ex: 10 dias → 5 dias)",
            "🔒 BLOQUEIO DE CRÉDITO: Sistema verifica automaticamente o limite de crédito do cliente. Se excedido, o pedido é bloqueado até liberação manual",
            "✅ Todos os campos obrigatórios devem estar preenchidos antes de avançar para PCP",
            "🟣 AGUARDANDO PARTIÇÃO: Pedidos com badge roxo 'Aguardando Decisão de Partição' foram sugeridos para divisão pelo PCP e aguardam decisão comercial"
        ],
        nextSteps: [
            "Revisar dados importados e validar os 19 campos obrigatórios",
            "Verificar se há bloqueio de crédito ativo",
            "Confirmar flags estratégicas (Exportação, Primeira Ordem, Reposição)",
            "Adicionar notas de customização para itens personalizados",
            "Para pedidos com badge roxo: Decidir sobre partição sugerida pelo PCP",
            "Mover para PCP quando validação comercial estiver completa"
        ],
        icon: "📋",
        requiredFields: [
            "19 campos da planilha Excel",
            "Descrição de customização (se item personalizado)",
            "Liberação de crédito (se bloqueado)"
        ]
    },

    PCP: {
        title: "PCP - Planejamento e Controle de Produção",
        description: "Análise técnica, mapeamento de SKUs e vinculação de custos de matéria-prima.",
        rules: [
            "🔗 MAPEAMENTO DE-PARA: Use o sistema de Alias para mapear SKUs similares (Ex: 'SKU-A' → 'SKU-MASTER'). Isso permite reutilizar custos e especificações técnicas",
            "💰 CUSTO OBRIGATÓRIO: Cada SKU DEVE ter custo de matéria-prima vinculado (R$/kg) antes de avançar para Produção",
            "📊 MOTOR DE MARGEM PCP: CM = (VP - Impostos 22.25% - Comissão - Frete) / Custos. Se Custos = 0 ou Nulo, a margem passa para o status 'PENDENTE PCP'",
            "🎨 LIMITES DE MARGEM: Verde (>= 30%), Amarelo (< 30%), Laranja (< 19%), Vermelho (< 10% ou negativa)",
            "📎 VALIDAÇÃO DE ANEXOS: Para itens personalizados de clientes novos, verificar se os anexos técnicos foram carregados corretamente",
            "🆘 BOTÃO 'SUGERIR PARTIÇÃO': Se houver falta de matéria-prima, use este botão para dividir o pedido em lotes menores baseado no estoque disponível",
            "📦 TIPO DE EMBALAGEM: Definir obrigatoriamente: Caixa, Saco, Pallet, Granel ou Outro",
            "⚠️ IMPEDIMENTOS: Registrar qualquer impedimento de produção (falta de MP, equipamento quebrado, etc.)",
            "📊 MARGEM: O sistema calcula automaticamente a margem de contribuição baseada nos custos vinculados"
        ],
        nextSteps: [
            "Acessar a página de Custos para vincular matéria-prima a cada SKU",
            "Usar o sistema De-Para (Alias) para SKUs similares",
            "Se houver falta de MP, clicar em 'Sugerir Partição' para dividir o pedido",
            "Validar anexos técnicos para itens personalizados",
            "Preencher metadados de produção (tipo de embalagem, rendimento)",
            "Mover para Produção/Embalagem quando todos os custos estiverem vinculados"
        ],
        icon: "📊",
        requiredFields: [
            "Custo de matéria-prima (custo_mp_kg) para cada SKU",
            "Rendimento (kg por unidade)",
            "Tipo de embalagem",
            "Mapeamento De-Para (se aplicável)"
        ]
    },

    "Produção/Embalagem": {
        title: "Produção/Embalagem - Fabricação e Controle de Qualidade",
        description: "Execução da produção, registro de quantidades reais e rastreamento automático de SLA.",
        rules: [
            "📊 QUANTIDADE REAL PRODUZIDA: Campo OBRIGATÓRIO - Registrar a quantidade efetivamente produzida (pode diferir da quantidade pedida)",
            "⏱️ RASTREAMENTO AUTOMÁTICO DE SLA: O sistema monitora automaticamente o tempo de produção e alerta quando o SLA está próximo do vencimento",
            "🔄 PEDIDOS DE REPOSIÇÃO: Lembrar que têm SLA reduzido em 50% - priorizar na fila de produção",
            "📉 PERDAS E REFUGOS: Registrar perdas de material e refugos para análise de eficiência",
            "⚠️ PROBLEMAS DE QUALIDADE: Documentar não-conformidades e problemas técnicos",
            "🔧 IMPEDIMENTOS: Atualizar status de impedimentos (equipamento, falta de insumo, etc.)",
            "✅ VALIDAÇÃO: Confirmar conformidade com especificações técnicas antes de avançar"
        ],
        nextSteps: [
            "Registrar a quantidade real produzida no campo específico",
            "Documentar perdas, refugos e não-conformidades (se houver)",
            "Atualizar impedimentos de produção",
            "Validar qualidade e conformidade com especificações",
            "Mover para Expedição/Faturamento quando produção estiver completa e aprovada"
        ],
        icon: "🏭",
        requiredFields: [
            "Quantidade real produzida (actual_produced_quantity)",
            "Status de qualidade",
            "Registro de perdas/refugos (se aplicável)"
        ]
    },

    "Faturamento/Expedição": {
        title: "Faturamento/Expedição - Preparação e Envio",
        description: "Embalagem final, sincronismo de despacho e preparação para envio ao cliente. Após conclusão, pedido avança para Financeiro.",
        rules: [
            "🔄 SINCRONISMO DE DESPACHO: Sistema EXIGE dois documentos obrigatórios antes de finalizar:",
            "   • PDF da Nota Fiscal (NF) - Upload obrigatório",
            "   • Foto da Carga - Registro fotográfico do produto embalado e pronto para envio",
            "📋 CHECKLIST LOGÍSTICO:",
            "   ✓ Verificar tipo de embalagem definido no PCP",
            "   ✓ Confirmar endereço de entrega do cliente",
            "   ✓ Gerar documentação de transporte (NF, DANFE, etc.)",
            "   ✓ Registrar data e hora de saída",
            "   ✓ Atualizar código de rastreamento da transportadora",
            "🌍 EXPORTAÇÃO: Para pedidos de exportação, verificar documentação alfandegária adicional",
            "📦 EMBALAGEM: Seguir rigorosamente o tipo de embalagem definido pelo PCP"
        ],
        nextSteps: [
            "Embalar produto conforme especificações do PCP",
            "Gerar Nota Fiscal e fazer upload do PDF no sistema",
            "Tirar foto da carga embalada e fazer upload",
            "Registrar transportadora e código de rastreamento",
            "Confirmar endereço de entrega",
            "Mover para Financeiro quando sincronismo de despacho estiver completo (NF + Foto)"
        ],
        icon: "📦",
        requiredFields: [
            "PDF da Nota Fiscal (upload obrigatório)",
            "Foto da Carga (upload obrigatório)",
            "Data de envio",
            "Transportadora",
            "Código de rastreamento"
        ]
    },

    Financeiro: {
        title: "Financeiro - Auditoria e Conclusão",
        description: "Pedidos despachados aguardando auditoria financeira final e conclusão. Inclui pedidos em AUDIT_PENDING e COMPLETED.",
        rules: [
            "💰 AUDITORIA FINANCEIRA: Revisão final de valores, comissões e margens",
            "📄 DOCUMENTAÇÃO COMPLETA: Validação de todos os documentos (NF, fotos, anexos técnicos)",
            "✅ PEDIDO DESPACHADO: Produto foi enviado ao cliente com sucesso",
            "🔗 BLOCKCHAIN AUDIT LOG: Cada transição de status foi registrada de forma imutável com:",
            "   • Timestamp exato da mudança",
            "   • Usuário responsável pela ação",
            "   • Status anterior e novo status",
            "   • Metadados adicionais (comentários, anexos, etc.)",
            "📊 MÉTRICAS REGISTRADAS: Performance de SLA, tempo de produção, perdas e eficiência foram capturadas",
            "🗄️ POLÍTICA DE ARMAZENAMENTO: Todos os dados são mantidos por 24 meses para auditoria e análise histórica",
            "📈 ANÁLISE DISPONÍVEL: Dados podem ser usados para relatórios gerenciais e melhoria contínua"
        ],
        nextSteps: [
            "Realizar auditoria financeira final",
            "Validar comissões e margens calculadas",
            "Confirmar recebimento de pagamento (se aplicável)",
            "Arquivar documentação física e digital",
            "Analisar métricas de performance e SLA",
            "Revisar Audit Log para auditoria interna",
            "Marcar como COMPLETED após auditoria aprovada"
        ],
        icon: "💰",
        auditFeatures: [
            "Auditoria financeira obrigatória",
            "Blockchain Audit Log completo",
            "Armazenamento de 24 meses",
            "Rastreabilidade total de mudanças",
            "Análise histórica disponível"
        ]
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
