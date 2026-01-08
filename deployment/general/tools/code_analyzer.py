"""Script d'analyse et d'amélioration continue du code."""
import ast
import os
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Tuple


class CodeAnalyzer:
    """Analyseur de code Python."""
    
    def __init__(self, root_dir: str):
        self.root_dir = Path(root_dir)
        self.stats = defaultdict(int)
        self.issues = []
    
    def analyze_file(self, file_path: Path):
        """Analyse un fichier Python."""
        try:
            content = file_path.read_text(encoding='utf-8')
            tree = ast.parse(content)
            
            # Statistiques de base
            self.stats['files'] += 1
            self.stats['lines'] += content.count('\n') + 1
            
            # Analyser les fonctions
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    self.stats['functions'] += 1
                    self._analyze_function(node, file_path)
                elif isinstance(node, ast.ClassDef):
                    self.stats['classes'] += 1
                    self._analyze_class(node, file_path)
        
        except SyntaxError as e:
            self.issues.append({
                'file': str(file_path),
                'type': 'syntax_error',
                'message': str(e),
                'severity': 'high'
            })
    
    def _analyze_function(self, node: ast.FunctionDef, file_path: Path):
        """Analyse une fonction."""
        # Vérifier la documentation
        docstring = ast.get_docstring(node)
        if not docstring and not node.name.startswith('_'):
            self.issues.append({
                'file': str(file_path),
                'line': node.lineno,
                'type': 'missing_docstring',
                'function': node.name,
                'message': f"Function '{node.name}' lacks documentation",
                'severity': 'low'
            })
        
        # Vérifier la complexité (nombre d'instructions)
        num_statements = sum(1 for _ in ast.walk(node) if isinstance(_, ast.stmt))
        if num_statements > 50:
            self.issues.append({
                'file': str(file_path),
                'line': node.lineno,
                'type': 'high_complexity',
                'function': node.name,
                'message': f"Function '{node.name}' has {num_statements} statements (consider refactoring)",
                'severity': 'medium'
            })
        
        # Vérifier le nombre de paramètres
        num_args = len(node.args.args)
        if num_args > 7:
            self.issues.append({
                'file': str(file_path),
                'line': node.lineno,
                'type': 'too_many_parameters',
                'function': node.name,
                'message': f"Function '{node.name}' has {num_args} parameters (consider using a config object)",
                'severity': 'medium'
            })
    
    def _analyze_class(self, node: ast.ClassDef, file_path: Path):
        """Analyse une classe."""
        # Vérifier la documentation
        docstring = ast.get_docstring(node)
        if not docstring:
            self.issues.append({
                'file': str(file_path),
                'line': node.lineno,
                'type': 'missing_docstring',
                'class': node.name,
                'message': f"Class '{node.name}' lacks documentation",
                'severity': 'low'
            })
        
        # Compter les méthodes
        methods = [n for n in node.body if isinstance(n, ast.FunctionDef)]
        if len(methods) > 20:
            self.issues.append({
                'file': str(file_path),
                'line': node.lineno,
                'type': 'large_class',
                'class': node.name,
                'message': f"Class '{node.name}' has {len(methods)} methods (consider splitting)",
                'severity': 'medium'
            })
    
    def analyze_directory(self, directory: Path = None):
        """Analyse tous les fichiers Python dans un répertoire."""
        if directory is None:
            directory = self.root_dir
        
        for file_path in directory.rglob('*.py'):
            # Ignorer les répertoires spéciaux
            if any(part.startswith('.') or part == '__pycache__' for part in file_path.parts):
                continue
            
            self.analyze_file(file_path)
    
    def get_report(self) -> Dict:
        """Génère un rapport d'analyse."""
        # Grouper les issues par type
        issues_by_type = defaultdict(list)
        for issue in self.issues:
            issues_by_type[issue['type']].append(issue)
        
        return {
            'stats': dict(self.stats),
            'issues_by_type': dict(issues_by_type),
            'issues_by_severity': {
                'high': [i for i in self.issues if i['severity'] == 'high'],
                'medium': [i for i in self.issues if i['severity'] == 'medium'],
                'low': [i for i in self.issues if i['severity'] == 'low']
            },
            'total_issues': len(self.issues)
        }


def print_report(report: Dict):
    """Affiche le rapport d'analyse."""
    print("\n" + "="*80)
    print("📊 RAPPORT D'ANALYSE DE CODE")
    print("="*80 + "\n")
    
    # Statistiques
    stats = report['stats']
    print("📈 Statistiques:")
    print(f"  Fichiers analysés: {stats.get('files', 0)}")
    print(f"  Lignes de code: {stats.get('lines', 0)}")
    print(f"  Classes: {stats.get('classes', 0)}")
    print(f"  Fonctions: {stats.get('functions', 0)}")
    
    # Issues par sévérité
    print(f"\n⚠️  Problèmes détectés: {report['total_issues']}")
    
    severity_emoji = {'high': '🔴', 'medium': '🟡', 'low': '🟢'}
    for severity in ['high', 'medium', 'low']:
        issues = report['issues_by_severity'][severity]
        if issues:
            print(f"\n{severity_emoji[severity]} {severity.upper()} ({len(issues)}):")
            for issue in issues[:5]:  # Afficher les 5 premiers
                file_name = Path(issue['file']).name
                location = f"{file_name}:{issue.get('line', '?')}"
                print(f"  - {location}: {issue['message']}")
            
            if len(issues) > 5:
                print(f"  ... et {len(issues) - 5} autres")
    
    # Issues par type
    print(f"\n📊 Par type:")
    for issue_type, issues in report['issues_by_type'].items():
        print(f"  {issue_type.replace('_', ' ').title()}: {len(issues)}")
    
    print("\n" + "="*80)


def generate_recommendations(report: Dict) -> List[str]:
    """Génère des recommandations d'amélioration."""
    recommendations = []
    
    # Recommandations basées sur les statistiques
    stats = report['stats']
    
    if stats.get('lines', 0) > 50000:
        recommendations.append(
            "🔄 Code base importante (>50k lignes) - considérer une refactorisation modulaire"
        )
    
    # Recommandations basées sur les issues
    issues_by_type = report['issues_by_type']
    
    if len(issues_by_type.get('missing_docstring', [])) > 20:
        recommendations.append(
            "📝 Améliorer la documentation - beaucoup de fonctions/classes sans docstring"
        )
    
    if len(issues_by_type.get('high_complexity', [])) > 5:
        recommendations.append(
            "🔀 Simplifier le code - plusieurs fonctions avec complexité élevée"
        )
    
    if len(issues_by_type.get('large_class', [])) > 3:
        recommendations.append(
            "🏗️  Refactoriser les grandes classes en composants plus petits"
        )
    
    # Recommandations basées sur la sévérité
    high_severity = len(report['issues_by_severity']['high'])
    if high_severity > 0:
        recommendations.append(
            f"🚨 URGENT: Corriger les {high_severity} problèmes de haute sévérité"
        )
    
    return recommendations


if __name__ == '__main__':
    import sys
    
    # Déterminer le répertoire racine
    if len(sys.argv) > 1:
        root_dir = sys.argv[1]
    else:
        root_dir = Path(__file__).parent / 'app'
    
    print(f"🔍 Analyse du code dans: {root_dir}")
    
    # Analyser
    analyzer = CodeAnalyzer(root_dir)
    analyzer.analyze_directory()
    
    # Générer le rapport
    report = analyzer.get_report()
    print_report(report)
    
    # Recommandations
    recommendations = generate_recommendations(report)
    if recommendations:
        print("\n💡 RECOMMANDATIONS:\n")
        for rec in recommendations:
            print(f"  {rec}\n")