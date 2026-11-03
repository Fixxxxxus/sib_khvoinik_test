"""Разовая перелинковка статей из БД: проставляет related тем, у кого он пуст.

Карта собрана по scripts/related_articles.py контент-фабрики и вычитана руками.
Статьи, у которых related уже заполнен (новые из фабрики), не трогаются.
Дубль rulonnyy-ili-posevnoy-gazon (старая статья из data.py) целью не ставим.
"""
from django.db import migrations

RELATED = {
    "rasteniya-dlya-landshaftnyh-dizaynerov-novosibirsk": [
        "sazhentsy-optom-novosibirsk", "pitomnik-rasteniy-novosibirsk", "pitomnik-hvoynyh-novosibirsk"],
    "pitomnik-hvoynyh-novosibirsk": [
        "pitomnik-rasteniy-novosibirsk", "kupit-hvoynye-novosibirsk", "hvoynye-leto-pochemu-zhelteet-hvoya"],
    "sazhentsy-optom-novosibirsk": [
        "rasteniya-dlya-landshaftnyh-dizaynerov-novosibirsk", "pitomnik-rasteniy-novosibirsk", "kak-vybrat-pitomnik-novosibirsk"],
    "kak-vybrat-pitomnik-novosibirsk": [
        "pitomnik-ili-sadovyy-centr", "pitomnik-rasteniy-novosibirsk", "kupit-hvoynye-novosibirsk"],
    "pitomnik-rasteniy-novosibirsk": [
        "pitomnik-hvoynyh-novosibirsk", "kak-vybrat-pitomnik-novosibirsk", "posadka-krupnomerov-novosibirsk"],
    "pitomnik-ili-sadovyy-centr": [
        "kak-vybrat-pitomnik-novosibirsk", "pitomnik-rasteniy-novosibirsk", "kupit-hvoynye-novosibirsk"],
    "kupit-hvoynye-novosibirsk": [
        "pitomnik-hvoynyh-novosibirsk", "hvoynye-leto-pochemu-zhelteet-hvoya", "posadka-krupnomerov-novosibirsk"],
    "posadka-krupnomerov-novosibirsk": [
        "pitomnik-rasteniy-novosibirsk", "kupit-hvoynye-novosibirsk", "ozelenenie-uchastka-novosibirsk"],
    "kogda-obrezat-lapchatku-kustarnikovuyu": [
        "osobennosti-klimata-sibiri", "vybor-rasteniy-dlya-tene", "pitomnik-rasteniy-novosibirsk"],
    "ozelenenie-uchastka-novosibirsk": [
        "vybor-rasteniy-dlya-tene", "posadka-krupnomerov-novosibirsk", "skolko-stoit-rulonnyy-gazon-pod-klyuch"],
    "uhod-za-gazonom-osenyu-sibir": [
        "uhod-za-gazonom-novosibirsk", "uhod-za-rulonnym-gazonom-posle-ukladki", "osobennosti-klimata-sibiri"],
    "uhod-za-gazonom-novosibirsk": [
        "uhod-za-rulonnym-gazonom-posle-ukladki", "uhod-za-gazonom-osenyu-sibir", "rulonnyy-gazon-v-zharu"],
    "uhod-za-rulonnym-gazonom-posle-ukladki": [
        "kak-ukladyvat-gazon", "rulonnyy-gazon-v-zharu", "uhod-za-gazonom-osenyu-sibir"],
    "podgotovka-uchastka-pod-rulonnyy-gazon": [
        "kak-ukladyvat-gazon", "skolko-stoit-rulonnyy-gazon-pod-klyuch", "rulonnyy-ili-posevnoy-gazon-sibir"],
    "rulonnyy-ili-posevnoy-gazon-sibir": [
        "skolko-stoit-rulonnyy-gazon-pod-klyuch", "podgotovka-uchastka-pod-rulonnyy-gazon", "kak-ukladyvat-gazon"],
    "skolko-stoit-rulonnyy-gazon-pod-klyuch": [
        "podgotovka-uchastka-pod-rulonnyy-gazon", "rulonnyy-ili-posevnoy-gazon-sibir", "kak-ukladyvat-gazon"],
}


def forwards(apps, schema_editor):
    Article = apps.get_model("pages", "Article")
    for slug, related in RELATED.items():
        obj = Article.objects.filter(slug=slug).first()
        if obj is not None and not obj.related:
            obj.related = related
            obj.save(update_fields=["related"])


def backwards(apps, schema_editor):
    Article = apps.get_model("pages", "Article")
    for slug, related in RELATED.items():
        Article.objects.filter(slug=slug, related=related).update(related=[])


class Migration(migrations.Migration):
    dependencies = [("pages", "0019_article_related")]
    operations = [migrations.RunPython(forwards, backwards)]
