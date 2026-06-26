import datetime

def get_easter_date(year):
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return datetime.date(year, month, day)

def get_br_rj_holidays(year):
    """
    Retorna um dicionário {datetime.date: "Nome do Feriado"}
    com os feriados nacionais do Brasil e específicos do Estado/Município do Rio de Janeiro.
    """
    easter = get_easter_date(year)
    
    # Feriados móveis baseados na Páscoa
    good_friday = easter - datetime.timedelta(days=2)
    carnival = easter - datetime.timedelta(days=47)
    carnival_monday = easter - datetime.timedelta(days=48)
    corpus_christi = easter + datetime.timedelta(days=60)
    
    holidays = {
        # Feriados Fixos Nacionais
        datetime.date(year, 1, 1): "Confraternização Universal",
        datetime.date(year, 4, 21): "Tiradentes",
        datetime.date(year, 5, 1): "Dia do Trabalhador",
        datetime.date(year, 9, 7): "Independência do Brasil",
        datetime.date(year, 10, 12): "Nossa Senhora Aparecida",
        datetime.date(year, 11, 2): "Finados",
        datetime.date(year, 11, 15): "Proclamação da República",
        datetime.date(year, 11, 20): "Dia da Consciência Negra",
        datetime.date(year, 12, 25): "Natal",
        
        # Feriados Estaduais / Municipais do RJ (Fixos)
        datetime.date(year, 1, 20): "São Sebastião (Padroeiro RJ)",
        datetime.date(year, 4, 23): "Dia de São Jorge",
        
        # Feriados Móveis
        carnival_monday: "Carnaval",
        carnival: "Terça-feira de Carnaval",
        good_friday: "Sexta-feira Santa",
        corpus_christi: "Corpus Christi",
    }
    return holidays
