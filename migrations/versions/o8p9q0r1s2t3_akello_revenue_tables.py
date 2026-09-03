"""Akello Revenue periods and monthly metrics + FY2027 seed."""

from datetime import datetime

from alembic import op
import sqlalchemy as sa

from app.migration_schema import table_exists


revision = "o8p9q0r1s2t3"
down_revision = "n7o8p9q0r1s2"
branch_labels = None
depends_on = None

# From Akello Revenue FY27.xlsx
FY2027_MONTHS = [
    # month, rev..., sub...
    (3, 6500, 0, 45000, 0, 223.35, 185, 196.44, 400.01, 49563, 0, 66186, 0, 170, 5, 36, 6),
    (4, 3000, 0, 15000, 0, 221.15, 370, 135.74, 59.2, 6581, 0, 17552, 0, 165, 8, 33, 1),
    (5, 6354, 0, 15569, 0, 131, 481, 1864, 223, 6354, 0, 10379, 0, 85, 2, 35, 2),
    (6, 23334, 0, 774, 0, 1531, 111, 149.8, 297.58, 2334, 0, 5166, 0, 78, 3, 45, 4),
    (7, 21113, 0, 35440, 0, 2309.49, 74, 569.78, 135188.56, 10354, 0, 22415, 0, 84, 2, 72, 730),
]


def upgrade():
    bind = op.get_bind()

    if not table_exists(bind, "akello_revenue_periods"):
        op.create_table(
            "akello_revenue_periods",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("code", sa.String(length=32), nullable=False),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("zig_usd_rate", sa.Numeric(precision=12, scale=4), nullable=True),
            sa.Column("created_by", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["created_by"], ["user.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_akello_revenue_periods_code",
            "akello_revenue_periods",
            ["code"],
            unique=True,
        )

    if not table_exists(bind, "akello_revenue_months"):
        op.create_table(
            "akello_revenue_months",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("period_id", sa.Integer(), nullable=False),
            sa.Column("month", sa.Integer(), nullable=False),
            sa.Column("rev_asl_hlf_usd", sa.Numeric(precision=14, scale=2), nullable=False),
            sa.Column("rev_asl_hlf_zwl", sa.Numeric(precision=14, scale=2), nullable=False),
            sa.Column("rev_lib_hlf_usd", sa.Numeric(precision=14, scale=2), nullable=False),
            sa.Column("rev_lib_hlf_zwl", sa.Numeric(precision=14, scale=2), nullable=False),
            sa.Column("rev_asl_org_usd", sa.Numeric(precision=14, scale=2), nullable=False),
            sa.Column("rev_asl_org_zwl", sa.Numeric(precision=14, scale=2), nullable=False),
            sa.Column("rev_lib_org_usd", sa.Numeric(precision=14, scale=2), nullable=False),
            sa.Column("rev_lib_org_zwl", sa.Numeric(precision=14, scale=2), nullable=False),
            sa.Column("sub_asl_hlf_usd", sa.Integer(), nullable=False),
            sa.Column("sub_asl_hlf_zwl", sa.Integer(), nullable=False),
            sa.Column("sub_lib_hlf_usd", sa.Integer(), nullable=False),
            sa.Column("sub_lib_hlf_zwl", sa.Integer(), nullable=False),
            sa.Column("sub_asl_org_usd", sa.Integer(), nullable=False),
            sa.Column("sub_asl_org_zwl", sa.Integer(), nullable=False),
            sa.Column("sub_lib_org_usd", sa.Integer(), nullable=False),
            sa.Column("sub_lib_org_zwl", sa.Integer(), nullable=False),
            sa.Column("updated_by", sa.Integer(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(
                ["period_id"],
                ["akello_revenue_periods.id"],
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(["updated_by"], ["user.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("period_id", "month", name="uq_akello_revenue_period_month"),
        )
        op.create_index(
            "ix_akello_revenue_months_period_id",
            "akello_revenue_months",
            ["period_id"],
            unique=False,
        )

    conn = op.get_bind()
    existing = conn.execute(
        sa.text("SELECT id FROM akello_revenue_periods WHERE code = :code"),
        {"code": "FY2027"},
    ).fetchone()
    if existing:
        return

    now = datetime.utcnow()
    result = conn.execute(
        sa.text(
            "INSERT INTO akello_revenue_periods "
            "(code, name, zig_usd_rate, created_by, created_at, updated_at) "
            "VALUES (:code, :name, NULL, NULL, :created_at, :updated_at)"
        ),
        {
            "code": "FY2027",
            "name": "Financial Year 2027",
            "created_at": now,
            "updated_at": now,
        },
    )
    # Get inserted id (works for SQLite/MySQL/Postgres via lastrowid or RETURNING-style)
    period_id = getattr(result, "lastrowid", None)
    if not period_id:
        row = conn.execute(
            sa.text("SELECT id FROM akello_revenue_periods WHERE code = :code"),
            {"code": "FY2027"},
        ).fetchone()
        period_id = row[0] if row else None
    if not period_id:
        return

    insert_sql = sa.text(
        """
        INSERT INTO akello_revenue_months (
            period_id, month,
            rev_asl_hlf_usd, rev_asl_hlf_zwl, rev_lib_hlf_usd, rev_lib_hlf_zwl,
            rev_asl_org_usd, rev_asl_org_zwl, rev_lib_org_usd, rev_lib_org_zwl,
            sub_asl_hlf_usd, sub_asl_hlf_zwl, sub_lib_hlf_usd, sub_lib_hlf_zwl,
            sub_asl_org_usd, sub_asl_org_zwl, sub_lib_org_usd, sub_lib_org_zwl,
            updated_by, updated_at
        ) VALUES (
            :period_id, :month,
            :rev_asl_hlf_usd, :rev_asl_hlf_zwl, :rev_lib_hlf_usd, :rev_lib_hlf_zwl,
            :rev_asl_org_usd, :rev_asl_org_zwl, :rev_lib_org_usd, :rev_lib_org_zwl,
            :sub_asl_hlf_usd, :sub_asl_hlf_zwl, :sub_lib_hlf_usd, :sub_lib_hlf_zwl,
            :sub_asl_org_usd, :sub_asl_org_zwl, :sub_lib_org_usd, :sub_lib_org_zwl,
            NULL, :updated_at
        )
        """
    )
    for row in FY2027_MONTHS:
        conn.execute(
            insert_sql,
            {
                "period_id": period_id,
                "month": row[0],
                "rev_asl_hlf_usd": row[1],
                "rev_asl_hlf_zwl": row[2],
                "rev_lib_hlf_usd": row[3],
                "rev_lib_hlf_zwl": row[4],
                "rev_asl_org_usd": row[5],
                "rev_asl_org_zwl": row[6],
                "rev_lib_org_usd": row[7],
                "rev_lib_org_zwl": row[8],
                "sub_asl_hlf_usd": row[9],
                "sub_asl_hlf_zwl": row[10],
                "sub_lib_hlf_usd": row[11],
                "sub_lib_hlf_zwl": row[12],
                "sub_asl_org_usd": row[13],
                "sub_asl_org_zwl": row[14],
                "sub_lib_org_usd": row[15],
                "sub_lib_org_zwl": row[16],
                "updated_at": now,
            },
        )


def downgrade():
    bind = op.get_bind()
    if table_exists(bind, "akello_revenue_months"):
        op.drop_table("akello_revenue_months")
    if table_exists(bind, "akello_revenue_periods"):
        op.drop_table("akello_revenue_periods")
