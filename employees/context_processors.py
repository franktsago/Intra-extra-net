"""Contexte de templates : département(s) de l'utilisateur courant.

Permet de conditionner l'affichage de rubriques selon le rattachement
(ex. « Digital & IT » réservé aux membres de ce département)."""


def user_departments(request):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated or not getattr(user, "is_internal", False):
        return {}
    emp = getattr(user, "employee", None)
    codes, names = set(), set()
    if emp:
        for d in emp.departments.all():
            if d.code:
                codes.add(d.code.upper())
            names.add(d.name.lower())
    is_digital_it = ("IT" in codes) or any("digital" in n for n in names)
    return {
        "my_dept_codes": codes,
        "is_digital_it": is_digital_it,
    }
