# EPL Formal Operational Semantics & Mathematical Foundations

**Specification Version: 11.0.0**

This document specifies the formal mathematical semantics of the core English Programming Language (EPL) using Structural Operational Semantics (SOS) and Big-Step reduction rules.

---

## 1. Syntactic Domains & Semantic Objects

- **Identifiers / Variables**: $x, y, z \in \mathbf{Var}$
- **Expressions**: $e \in \mathbf{Expr}$
- **Statements**: $s \in \mathbf{Stmt}$
- **Values**: $v \in \mathbf{Val} = \mathbb{Z} \cup \mathbb{R} \cup \mathbb{B} \cup \mathbf{String} \cup \{\mathbf{nil}\}$
- **State / Environment**: $\sigma \in \mathbf{Env} = \mathbf{Var} \to \mathbf{Val}$

Evaluation judgment:
$$\langle \sigma, e \rangle \Downarrow \langle \sigma', v \rangle$$
denotes that expression $e$ in state $\sigma$ evaluates to value $v$ resulting in state $\sigma'$.

---

## 2. Big-Step Reduction Rules

### Literals
$$\frac{}{\langle \sigma, n \rangle \Downarrow \langle \sigma, n \rangle} \quad (\text{Const-Int})$$

$$\frac{}{\langle \sigma, \text{true} \rangle \Downarrow \langle \sigma, \text{true} \rangle} \quad (\text{Const-Bool})$$

### Variable Lookup
$$\frac{\sigma(x) = v}{\langle \sigma, x \rangle \Downarrow \langle \sigma, v \rangle} \quad (\text{Var-Eval})$$

### Binary Arithmetic
$$\frac{\langle \sigma, e_1 \rangle \Downarrow \langle \sigma_1, n_1 \rangle \quad \langle \sigma_1, e_2 \rangle \Downarrow \langle \sigma_2, n_2 \rangle \quad n = n_1 \oplus n_2}{\langle \sigma, e_1 \oplus e_2 \rangle \Downarrow \langle \sigma_2, n \rangle} \quad (\text{BinOp-Eval})$$

### Variable Declaration & Assignment
$$\frac{\langle \sigma, e \rangle \Downarrow \langle \sigma_1, v \rangle}{\langle \sigma, \text{Create } x = e \rangle \Downarrow \sigma_1[x \mapsto v]} \quad (\text{Var-Decl})$$

$$\frac{\langle \sigma, e \rangle \Downarrow \langle \sigma_1, v \rangle \quad x \in \text{dom}(\sigma_1)}{\langle \sigma, \text{Set } x \text{ to } e \rangle \Downarrow \sigma_1[x \mapsto v]} \quad (\text{Var-Assign})$$

### Conditionals (If-Then-Else)
$$\frac{\langle \sigma, e_{cond} \rangle \Downarrow \langle \sigma_1, \text{true} \rangle \quad \langle \sigma_1, s_1 \rangle \Downarrow \sigma_2}{\langle \sigma, \text{If } e_{cond} \text{ Then } s_1 \text{ Else } s_2 \rangle \Downarrow \sigma_2} \quad (\text{If-True})$$

$$\frac{\langle \sigma, e_{cond} \rangle \Downarrow \langle \sigma_1, \text{false} \rangle \quad \langle \sigma_1, s_2 \rangle \Downarrow \sigma_2}{\langle \sigma, \text{If } e_{cond} \text{ Then } s_1 \text{ Else } s_2 \rangle \Downarrow \sigma_2} \quad (\text{If-False})$$

### While Loops
$$\frac{\langle \sigma, e_{cond} \rangle \Downarrow \langle \sigma_1, \text{false} \rangle}{\langle \sigma, \text{While } e_{cond} \text{ do } s \rangle \Downarrow \sigma_1} \quad (\text{While-False})$$

$$\frac{\langle \sigma, e_{cond} \rangle \Downarrow \langle \sigma_1, \text{true} \rangle \quad \langle \sigma_1, s \rangle \Downarrow \sigma_2 \quad \langle \sigma_2, \text{While } e_{cond} \text{ do } s \rangle \Downarrow \sigma_3}{\langle \sigma, \text{While } e_{cond} \text{ do } s \rangle \Downarrow \sigma_3} \quad (\text{While-True})$$

---

## 3. Semantic Soundness & Determinism Theorems

1. **Determinism**: For all closed expressions $e$ and states $\sigma$, if $\langle \sigma, e \rangle \Downarrow \langle \sigma_1, v_1 \rangle$ and $\langle \sigma, e \rangle \Downarrow \langle \sigma_2, v_2 \rangle$, then $\sigma_1 = \sigma_2$ and $v_1 = v_2$.
2. **Type Preservation (Subject Reduction)**: If $\Gamma \vdash e : \tau$ and $\langle \sigma, e \rangle \Downarrow \langle \sigma', v \rangle$, then $\Gamma \vdash v : \tau$.
