test='''
Taux d'overhead appliqué pour des subsides octroyés par les agences de financements publics 70 (état au 1.1.2019)
'''

print(len(test))
def is_table_of_contents(text: str) -> bool:
    # Détecter les patterns typiques
    dot_ratio = text.count('.') / len(text)
    has_toc_header = any(x in text.lower() for x in ['table des matières', 'table of contents', 'sommaire'])
    print(dot_ratio, has_toc_header)
    return dot_ratio > 0.1 and has_toc_header

is_table_of_contents(test)