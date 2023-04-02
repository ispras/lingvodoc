
"""Fully dynamic ToC

Revision ID: 2fd520393cc5
Revises: be06149acd44
Create Date: 2023-04-02 17:12:31.988687

"""


# revision identifiers, used by Alembic.
revision = '2fd520393cc5'
down_revision = 'be06149acd44'
branch_labels = None
depends_on = None


from lingvodoc.models import Language
from lingvodoc.utils import ids_to_id_query


from alembic import op
from sqlalchemy import func, tuple_


standard_language_id_list = [
  (1574, 116655), # Altai
  (33, 88), # Altai language
  (252, 40), # Altai-Kizhi dialect
  (1076, 4), # Altaic family
  (1574, 269058), # Azeric
  (1068, 5), # Baltic-Finnish
  (500, 121), # Bashkir
  (1076, 22), # Buryat language
  (33, 90), # Chalkan dialect
  (216, 8), # Chulym
  (1574, 272286), # Chuvash
  (295, 8), # Chuvash language
  (1100, 4), # Crimean Tatar
  (1105, 28), # Dolgan language
  (508, 49), # Enets
  (508, 39), # Erzya
  (633, 23), # Evenki
  (1552, 1252), # Finnish
  (508, 46), # Hungarian
  (1733, 13468), # Izhor
  (1501, 42640), # Japonic languages
  (1501, 42646), # Japonic proper
  (1311, 23), # Japono-Koreanic subfamily
  (1076, 10), # Kalmyk language
  (1552, 652), # Kamas
  (508, 37), # Karelian
  (500, 124), # Kazakh
  (500, 123), # Khakas
  (1574, 269111), # Khamnigan Evenki
  (508, 44), # Khanty
  (508, 42), # Komi
  (1076, 119), # Korean
  (1574, 99299), # Kur-Urmi Evenki
  (1574, 274491), # Manchu branch
  (508, 45), # Mansi
  (508, 41), # Mari
  (508, 40), # Moksha
  (1076, 7), # Mongolic languages
  (633, 17), # Nanii
  (1209, 24), # Negidal
  (1209, 20), # Negidal language
  (508, 48), # Nenets
  (508, 50), # Nganasan
  (1088, 612), # Noghai
  (1311, 41), # Northern Mongolic
  (1574, 203685), # Oghuz
  (1479, 599), # Oroch language
  (996, 1069), # Orok
  (1401, 11742), # Qara-Nogay
  (1574, 272495), # Qarachaj-Balkar language
  (998, 5), # Qumyq language
  (1574, 116715), # Qypčaq branch
  (508, 38), # Saami
  (508, 47), # Samoyed
  (1372, 10768), # Seber-Tatar
  (508, 51), # Selkup
  (1557, 6), # Shor
  (1574, 268977), # Solon language
  (500, 122), # Tatar
  (65, 2), # Telengit dialect
  (1251, 6), # Tofa
  (1574, 116679), # Tuba language
  (633, 16), # Tungus-Manchu languages
  (1002, 12), # Tungusic
  (1068, 9), # Turkic languages
  (1574, 269088), # Turkish
  (1574, 203688), # Turkmenic
  (1550, 3373), # Tuva
  (508, 43), # Udmurt
  (643, 4), # Udyhe language
  (33, 89), # Ujguri language
  (633, 22), # Ulcha
  (508, 36), # Uralic
  (840, 6), # Uzbek
  (1632, 6), # Veps
  (1372, 11240), # Volga Tatar
  (2108, 13), # Votic
  (1574, 274494), # Xibe
  (678, 9), # Yakut
]


def upgrade():

    op.execute(

        Language.__table__

            .update()

            .where(

                tuple_(
                    Language.client_id,
                    Language.object_id)

                    .in_(
                        ids_to_id_query(
                            standard_language_id_list)))

            .values(

                additional_metadata =

                    func.jsonb_set(
                        Language.additional_metadata,
                        '{toc_mark}',
                        func.to_jsonb(True),
                        True)))


def downgrade():

    op.execute(

        Language.__table__

            .update()

            .where(

                tuple_(
                    Language.client_id,
                    Language.object_id)

                    .in_(
                        ids_to_id_query(
                            standard_language_id_list)))

            .values(

                additional_metadata =

                    Language.additional_metadata - 'toc_mark'))

