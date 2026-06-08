/**
 * FlexFlow - Sistema de Ajuda Contextual
 * Configuração de ajuda para cada etapa do Kanban e Mesa de Conferência
 */

export const HELP_CONFIG = {
    Staging: {
        title: "Mesa de Conferência - Sistema de Ajuda Contextual - FlexFlow",
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
            "🔒 BLOQUEIO DE CONFIRMAÇÃO: Não é possível confirmar PO com erros pendentes ou itens não checados",
            "🚚 RATEIO DE CUSTOS ADICIONAIS: Frete e Custos Adicionais informados no cabeçalho são rateados proporcionalmente entre todos os itens para o cálculo da margem individual.",
            "💸 REGRA DO FINANCIAL GATE: Pedidos que excedem o limite de crédito do cliente são bloqueados automaticamente pelo Financial Gate, necessitando de liberação manual.",
            "🔄 BYPASS DE TROCA/REPOSIÇÃO: Itens bloqueados marcados com a flag de 'Troca/Reposição' ativam o bypass financeiro e recebem o status 'CRÉDITO PRÉ-APROVADO (TROCA)'.",
            "📦 SELEÇÃO DE EMBALAGEM OBRIGATÓRIA: O tipo de embalagem deve ser selecionado obrigatoriamente na Mesa de Conferência antes de confirmar o pedido.",
            "🏢 SELEÇÃO DE UNIDADE DE NEGÓCIO OBRIGATÓRIA: A Unidade de Negócio ('Indústria', 'Construção Civil' ou 'Varejo') deve ser selecionada de forma obrigatória. Esta escolha alimenta a inteligência de memória do cliente (sendo pré-preenchida no próximo import) e os indicadores de performance do Dashboard corporativo."
        ],
        nextSteps: [
            "Revisar cada item importado no painel de staging",
            "Selecionar a Unidade de Negócio correspondente para cada pedido no lote",
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
            "Unidade de Negócio selecionada",
            "Todos os itens marcados como 'Checado' (100%)"
        ],
        criticalRules: [
            "🚫 REGRA 100%: Impossível confirmar sem todos os itens checados",
            "⚠️ PAINEL DE RISCO: Monitora erros em tempo real",
            "🏢 UNIDADE DE NEGÓCIO: Preenchimento obrigatório para liberação do pedido"
        ]
    },

    Comercial: {
        title: "Comercial - Validação e Processamento Inicial",
        description: "Pedidos aguardando análise comercial. Inclui pedidos SUBMITTED e aqueles aguardando decisão de partição (WAITING_COMMERCIAL_PARTITION).",
        rules: [
            "📊 INTEGRAÇÃO S3 (AUTOMÁTICA): Os pedidos são ingeridos continuamente de forma automática através do bucket S3. A planilha Excel serve apenas como contingência/fallback de emergência caso haja indisponibilidade do S3.",
            "📝 NOTAS OBRIGATÓRIAS: Itens personalizados DEVEM ter descrição da customização preenchida",
            "🌍 FLAG EXPORTAÇÃO: Pedidos de exportação são marcados automaticamente e têm prioridade visual no Kanban",
            "⭐ FLAG PRIMEIRO PEDIDO: O Primeiro Pedido do cliente recebe atenção especial para garantir qualidade e validação de especificações",
            "🔄 Pedidos de Reposição (Troca): Redução de 50% no SLA (barra ciano)",
            "🔒 BLOQUEIO DE CRÉDITO: Sistema verifica automaticamente o limite de crédito do cliente. Se excedido, o pedido é bloqueado até liberação manual",
            "✅ Todos os campos obrigatórios devem estar preenchidos antes de avançar para PCP",
            "🟣 AGUARDANDO PARTIÇÃO: Pedidos com badge roxo 'Aguardando Decisão de Partição' foram sugeridos para divisão pelo PCP e aguardam decisão comercial",
            "🟣 Partição de Pedido: C1 mantém a data original; C2 recebe a nova data sugerida pelo PCP.",
            "⏱️ SLA DO PEDIDO: O SLA não para durante a espera de insumos (Transparência Total)."
        ],
        nextSteps: [
            "Revisar dados importados e validar todos os campos obrigatórios",
            "Verificar se há bloqueio de crédito ativo",
            "Confirmar flags estratégicas (Exportação, Primeiro Pedido, Troca/Reposição)",
            "Adicionar notas de customização para itens personalizados",
            "Para pedidos com badge roxo: Decidir sobre partição sugerida pelo PCP",
            "Mover para PCP quando validação comercial estiver completa"
        ],
        icon: "📋",
        requiredFields: [
            "Campos obrigatórios integrados via S3 ou planilha Excel de fallback",
            "Descrição de customização (se item personalizado)",
            "Liberação de crédito (se bloqueado)"
        ]
    },

    PCP: {
        title: "PCP - Planejamento e Controle de Produção",
        description: "Análise técnica, mapeamento de SKUs e vinculação de custos de matéria-prima.",
        rules: [
            "🔗 VÍNCULO DE SKU / NOME AMIGÁVEL: Use o sistema de Vínculo de SKU / Nome Amigável para mapear SKUs similares (Ex: 'SKU-A' → 'SKU-MASTER'). Isso permite reutilizar custos e especificações técnicas",
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
            "Usar o sistema de Vínculo de SKU / Nome Amigável para SKUs similares",
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
            "Vínculo de SKU / Nome Amigável (se aplicável)"
        ]
    },

    "Produção/Embalagem": {
        title: "Produção/Embalagem - Fabricação e Controle de Qualidade",
        description: "Execução da produção, registro de quantidades reais e rastreamento automático de SLA.",
        rules: [
            "📊 QUANTIDADE REAL PRODUZIDA: Campo OBRIGATÓRIO - Registrar a quantidade efetivamente produzida (pode diferir da quantidade pedida)",
            "⏱️ SLA: Cronômetro contínuo. O SLA não para durante a espera de insumos (Transparência Total)",
            "🔄 Pedidos de Reposição: Redução de 50% no SLA (barra ciano) - priorizar na fila de produção",
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
        description: "Embalagem final, sincronismo de despacho e preparação para envio ao cliente.",
        rules: [
            "🔄 PORTÃO DE EXPEDIÇÃO: O fechamento do pedido exige obrigatoriamente o número da NF-e (que se refere ao Número da Nota Fiscal/Invoice Number, e não à chave de acesso XML de 44 dígitos), o PDF da Nota Fiscal e fotos anexas (Canhoto Assinado e Carga).",
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
            "Número da NF-e (Invoice Number)",
            "PDF da Nota Fiscal (NF)",
            "Foto da Carga (Canhoto Assinado e Carga)",
            "Data de envio",
            "Transportadora",
            "Código de rastreamento"
        ]
    },

    Financeiro: {
        title: "Financeiro - Controle de Crédito",
        description: "Exclusivo para análise e liberação de bloqueios de crédito.",
        rules: [
            "🔒 ANÁLISE DE CRÉDITO: Esta etapa é exclusiva para análise e liberação de bloqueios de crédito baseados no histórico e limite financeiro do cliente.",
            "✅ LIBERAÇÃO FINANCEIRA: Aprovadores autorizados revisam a justificativa comercial anexada para autorizar ou recusar o prosseguimento do pedido.",
            "🔄 BYPASS DE TROCA: Pedidos sinalizados como Troca/Reposição têm liberação de crédito automática (Crédito Pré-Aprovado).",
            "🔗 BLOCKCHAIN AUDIT LOG: Toda alteração de status e liberação é registrada com assinatura hash de forma imutável, garantindo auditoria completa."
        ],
        nextSteps: [
            "Revisar o limite de crédito do cliente",
            "Analisar a justificativa comercial anexada ao pedido bloqueado",
            "Mover para PCP/Aprovados após liberação de crédito concedida"
        ],
        icon: "💰",
        auditFeatures: [
            "Análise exclusiva de liberação de crédito",
            "Blockchain Audit Log completo",
            "Rastreabilidade total de mudanças",
            "Auditoria de justificativas comerciais"
        ]
    },

    "Concluídos": {
        title: "Concluídos - Histórico e Auditoria",
        description: "Repositório histórico para consulta de pedidos finalizados e auditoria de Timeline.",
        rules: [
            "📂 HISTÓRICO IMUTÁVEL: Pedidos concluídos servem como registro histórico permanente.",
            "⏱️ SLA FINALIZADO: O cronômetro de SLA está encerrado e registrado para fins de indicadores de performance (KPIs).",
            "🔗 AUDITORIA COMPLETA: Toda a timeline e o log de transições de status (Audit Log) estão disponíveis para consulta."
        ],
        nextSteps: [
            "Consultar métricas de SLA e lead time no Dashboard",
            "Verificar logs de auditoria caso necessário"
        ],
        icon: "📂",
        requiredFields: [],
        criticalRules: [
            "🔒 IMUTABILIDADE: Não é possível mover pedidos fora desta coluna sem justificativa de exceção de auditoria"
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
        label: "Primeiro Pedido",
        icon: "⭐",
        color: "yellow",
        tooltip: "Primeiro pedido do cliente - Prioridade para garantir qualidade e impressão positiva"
    },
    is_replacement: {
        label: "Troca/Reposição",
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
