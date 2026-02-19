from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Dict, List, Tuple
import re
import unicodedata


@dataclass
class ToolResult:
    success: bool
    output: str


@dataclass
class Tool:
    name: str
    description: str
    keywords: Tuple[str, ...]
    handler: Callable[[str, "OpenClawAgent"], ToolResult]


class OpenClawAgent:
    """Agente conversacional simples com planejamento por intenção."""

    def __init__(self, name: str = "OpenClaw Agent", memory_limit: int = 80) -> None:
        self.name = name
        self.memory_limit = memory_limit
        self.tools: Dict[str, Tool] = {}
        self.memory: List[str] = []

    def add_tool(self, tool: Tool) -> None:
        self.tools[tool.name] = tool

    def remember(self, role: str, message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.memory.append(f"[{timestamp}] {role}: {message}")
        if len(self.memory) > self.memory_limit:
            self.memory = self.memory[-self.memory_limit :]

    def _normalize(self, text: str) -> str:
        normalized = unicodedata.normalize("NFKD", text)
        without_accent = "".join(char for char in normalized if not unicodedata.combining(char))
        return without_accent.lower()

    def _intent_score(self, tool: Tool, task: str) -> int:
        normalized_task = self._normalize(task)
        score = 0
        for keyword in tool.keywords:
            if re.search(rf"\b{re.escape(keyword)}\b", normalized_task):
                score += 2
            elif keyword in normalized_task:
                score += 1
        return score

    def plan(self, task: str) -> List[Tool]:
        ranked_tools = sorted(
            ((self._intent_score(tool, task), tool) for tool in self.tools.values()),
            key=lambda item: item[0],
            reverse=True,
        )
        return [tool for score, tool in ranked_tools if score > 0]

    def run(self, task: str) -> ToolResult:
        self.remember("Usuário", task)

        if not self.tools:
            result = ToolResult(False, "Nenhuma ferramenta cadastrada no agente.")
            self.remember("Agente", result.output)
            return result

        plan = self.plan(task)
        if not plan:
            fallback = self.tools["ajuda"] if "ajuda" in self.tools else next(iter(self.tools.values()))
            result = fallback.handler(task, self)
            self.remember("Agente", result.output)
            return result

        outputs: List[str] = []
        for tool in plan:
            result = tool.handler(task, self)
            outputs.append(f"[{tool.name}]\n{result.output}")
            if not result.success:
                break

        final_output = "\n\n".join(outputs)
        self.remember("Agente", final_output)
        return ToolResult(True, final_output)

    def list_tools(self) -> str:
        lines = ["Ferramentas disponíveis:"]
        for tool in self.tools.values():
            lines.append(f"- {tool.name}: {tool.description}")
        return "\n".join(lines)

    def show_memory(self, max_items: int = 10) -> str:
        if not self.memory:
            return "Memória vazia."
        excerpt = self.memory[-max_items:]
        return "\n".join(excerpt)

    def chat(self) -> None:
        print(f"{self.name} pronto.")
        print("Comandos: /tools, /memory, /clear, sair")
        while True:
            user_input = input("> ").strip()
            if not user_input:
                continue

            if user_input.lower() in {"sair", "exit", "quit"}:
                print("Até logo!")
                return
            if user_input == "/tools":
                print(self.list_tools())
                continue
            if user_input == "/memory":
                print(self.show_memory())
                continue
            if user_input == "/clear":
                self.memory.clear()
                print("Memória limpa.")
                continue

            result = self.run(user_input)
            print(result.output)


def tool_help(_: str, agent: OpenClawAgent) -> ToolResult:
    return ToolResult(
        True,
        "Eu sou um agente estilo OpenClaw para o Assinador Livre. "
        "Posso explicar assinatura, autenticação, hash, listar recursos e memória.\n\n"
        f"{agent.list_tools()}",
    )


def tool_signing_guide(task: str, _: OpenClawAgent) -> ToolResult:
    lines = [
        "Passo a passo para assinar no Assinador Livre:",
        "1) Execute `python main.py`.",
        "2) Clique em Browser e escolha um PDF ou DOCX.",
        "3) Preencha o nome do assinante e clique em 'Gerar Hash'.",
        "4) (Opcional) Escolha uma imagem transparente para a assinatura.",
        "5) Clique em 'Assinar documento' e selecione onde salvar.",
    ]

    normalized_task = task.lower()
    if "pdf" in normalized_task:
        lines.append("Dica PDF: o carimbo com hash/nome/data é aplicado em todas as páginas.")
    if "docx" in normalized_task:
        lines.append("Dica DOCX: os dados são adicionados ao final do documento.")

    return ToolResult(True, "\n".join(lines))


def tool_auth_guide(task: str, _: OpenClawAgent) -> ToolResult:
    output = [
        "Como autenticar a hash:",
        "1) Gere a hash durante o processo de assinatura.",
        "2) Copie a hash exibida no popup.",
        "3) Cole no campo 'Insira a hash para autenticar'.",
        "4) Clique em 'Autenticar'.",
        "5) O app informará se a hash está na memória da sessão atual.",
    ]
    if "erro" in task.lower() or "falha" in task.lower():
        output.append("Se der falha, confirme se você está na mesma execução do app que gerou a hash.")
    return ToolResult(True, "\n".join(output))


def tool_hash_explanation(_: str, __: OpenClawAgent) -> ToolResult:
    return ToolResult(
        True,
        "A hash é um identificador SHA-256 gerado com base no nome do assinante e no horário. "
        "Ela funciona como código de autenticação dentro da sessão do aplicativo.",
    )


def build_openclaw_agent() -> OpenClawAgent:
    agent = OpenClawAgent()
    agent.add_tool(
        Tool(
            name="ajuda",
            description="Explica capacidades do agente e mostra ferramentas.",
            keywords=("ajuda", "help", "oi", "ola", "menu", "comandos"),
            handler=tool_help,
        )
    )
    agent.add_tool(
        Tool(
            name="guia-assinatura",
            description="Ensina como assinar PDF e DOCX no app.",
            keywords=("assinar", "assinatura", "pdf", "docx", "documento"),
            handler=tool_signing_guide,
        )
    )
    agent.add_tool(
        Tool(
            name="guia-autenticacao",
            description="Explica como validar a hash no aplicativo.",
            keywords=("autenticar", "autenticacao", "validar", "falha", "erro"),
            handler=tool_auth_guide,
        )
    )
    agent.add_tool(
        Tool(
            name="explicar-hash",
            description="Descreve o papel da hash na assinatura.",
            keywords=("hash", "codigo", "sha", "seguranca"),
            handler=tool_hash_explanation,
        )
    )
    return agent


if __name__ == "__main__":
    build_openclaw_agent().chat()
