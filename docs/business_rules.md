# Business Rules: Financial Logic & Formulas

This document details the financial equations, rules, and mathematical proofs used throughout the FlexFlow system.

## 1. Present Value (VP) Calculation

The Present Value ($VP$) of a Purchase Order represents its value adjusted for the time-value of money, based on the arithmetic average of the payment terms (in days) and a standard discount rate.

### Mathematical Formula

$$VP = \frac{\text{TotalValue}}{1.025^{(\text{AverageDays} / 30)}}$$

Where:
*   $\text{TotalValue}$ is the gross value of the purchase order.
*   $\text{AverageDays}$ is the **Arithmetic Average** of the installment days.
*   The discount rate is fixed at $2.5\%$ per $30$ days (compounded).

### Payment Terms Parsing and Extraction

Payment terms are stored as string descriptions (e.g., `'10/20/30 DDL'`, `'30-60-90 DDL'`, or `'45 DDL'`). To calculate the arithmetic average of days:
1.  Strip occurrences of `'DDL'` (case-insensitive).
2.  Strip trailing and leading hyphens, spaces, and punctuation.
3.  Split the numbers using delimiters (slashes `/`, hyphens `-`, or commas `,`).
4.  Convert each term to a numeric float value.
5.  Compute the arithmetic average ($\text{AverageDays}$):
    $$\text{AverageDays} = \frac{d_1 + d_2 + \dots + d_n}{n}$$

#### Examples:
*   `'30/60/90 DDL'` $\rightarrow$ Terms: $[30, 60, 90]$ $\rightarrow$ AverageDays: $60.0$
*   `'45 DDL'` $\rightarrow$ Terms: $[45]$ $\rightarrow$ AverageDays: $45.0$

### Code Proof and Verification

The python implementation in `backend/services/financial_service.py` computes Present Value as follows:

```python
def calculate_vp(total_value: float, payment_terms: str) -> float:
    # 1. Parse days from payment terms
    days = []
    # Clean string: remove "DDL", replace separators with spaces
    cleaned = payment_terms.upper().replace("DDL", "").replace("/", " ").replace("-", " ").replace(",", " ")
    for word in cleaned.split():
        try:
            days.append(float(word))
        except ValueError:
            continue
            
    if not days:
        return total_value
        
    # 2. Arithmetic average of days
    average_days = sum(days) / len(days)
    
    # 3. Present value calculation
    vp = total_value / (1.025 ** (average_days / 30.0))
    return round(vp, 4)
```

The frontend Javascript implementation in `frontend/src/utils/marginCalculator.js` mirrors this logic exactly:

```javascript
export function calculateVP(totalValue, paymentTerms) {
  if (!paymentTerms) return totalValue;
  
  const cleaned = paymentTerms.toUpperCase().replace(/DDL/g, '').replace(/[\/,-]/g, ' ');
  const days = cleaned.split(/\s+/).map(Number).filter(n => !isNaN(n) && n > 0);
  
  if (days.length === 0) return totalValue;
  
  const averageDays = days.reduce((sum, d) => sum + d, 0) / days.length;
  const vp = totalValue / Math.pow(1.025, averageDays / 30.0);
  return Number(vp.toFixed(4));
}
```
