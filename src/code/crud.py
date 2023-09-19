from typing import Any, Dict, List, Optional, Union

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app import schemas
from app.crud.base import CRUDBase
from app.models.job_combinations import JobCombinations
from app.models.job_materials_uploaded import JobMaterialsUploaded
from app.models.job_outputs import JobOutputs
from app.models.jobs import Jobs, JobStatus
from app.models.user import User


class CRUDJobs(CRUDBase[Jobs, schemas.JobsCreate, schemas.JobsUpdate]):
    def get(self, db: Session, id: int) -> Optional[Jobs]:
        return db.query(Jobs).filter(Jobs.id == id).first()

    def get_count(self, db: Session, *, age, gender, user_id: Union[int, List[int]], sort_by, search_text) -> int:
        if isinstance(user_id, int):
            user_id = [user_id]
        filters = [Jobs.status != JobStatus.deleted.value]
        if age is not None:
            filters.append(Jobs.target_age == age)
        if gender is not None:
            filters.append(Jobs.target_gender == gender)
        if user_id is not None:
            filters.append(Jobs.user_id.in_(user_id))
        if search_text is not None:
            users = db.query(User).filter(User.name.like(f"%{search_text}%")).with_entities(User.id).all()
            users = [id[0] for id in users]
            filters.append(or_(Jobs.user_id.in_(users), Jobs.name.like(f"%{search_text}%")))
        sort_by_query = Jobs.created_at.desc() if sort_by == "desc" else Jobs.created_at.asc()
        return db.query(Jobs).filter(*filters).order_by(sort_by_query).count()

    def get_max_job_number(self, db: Session, *, user_id: int):
        max_job_number = (
            db.query(Jobs.job_number.label("max_job_number"))
            .filter(Jobs.user_id == user_id)
            .order_by(Jobs.job_number.desc())
            .first()
        )
        if max_job_number is None or max_job_number[0] is None:
            return 0
        return max_job_number[0]

    def create(self, db: Session, *, obj_in: Union[schemas.JobsCreate, schemas.JobsWithInfoCreate]) -> Jobs:
        create_data = obj_in.dict()
        db_obj = Jobs(**create_data)
        db.add(db_obj)
        db.commit()

        return db_obj

    def update(self, db: Session, *, db_obj: Jobs, obj_in: Union[schemas.JobsUpdate, Dict[str, Any]]) -> Jobs:
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.dict(exclude_unset=True)

        return super().update(db=db, db_obj=db_obj, obj_in=update_data)

    def get_multi(
        self,
        db: Session,
        *,
        skip: int = 0,
        limit: int = 5000,
        age: int = None,
        gender: int = None,
        user_id: Union[List[int], int] = None,
        sort_by: str = "desc",
        search_text: str = None,
    ) -> List[Jobs]:
        if isinstance(user_id, int):
            user_id = [user_id]
        filters = [Jobs.status != JobStatus.deleted.value]
        if age is not None:
            filters.append(Jobs.target_age == age)
        if gender is not None:
            filters.append(Jobs.target_gender == gender)
        if user_id is not None:
            filters.append(Jobs.user_id.in_(user_id))
        if search_text is not None:
            users = db.query(User).filter(User.name.like(f"%{search_text}%")).with_entities(User.id).all()
            users = [id[0] for id in users]
            filters.append(or_(Jobs.user_id.in_(users), Jobs.name.like(f"%{search_text}%")))
        sort_by_query = Jobs.created_at.desc() if sort_by == "desc" else Jobs.created_at.asc()
        return db.query(Jobs).filter(*filters).order_by(sort_by_query).offset(skip).limit(limit).all()

    def get_outputs(self, db: Session, job_id: int, limit: int = 3):
        result = (
            db.query(JobOutputs)
            .join(JobCombinations, JobOutputs.job_comb_id == JobCombinations.id)
            .filter(
                JobCombinations.job_id == job_id,
                JobOutputs.evaluation_score_Q1.isnot(None),
                JobOutputs.evaluation_score_Q2.isnot(None),
                JobOutputs.evaluation_score_Q3.isnot(None),
                JobOutputs.evaluation_score_Q4.isnot(None),
                JobOutputs.evaluation_score_Q5.isnot(None),
                JobOutputs.evaluation_score_Q6.isnot(None),
            )
            .all()
        )

        avgs = [1.260569, 1.248556, 1.332389, 1.382458, 1.485417, 1.374333]
        avgs = [r / 3 * 5 for r in avgs]

        outputs = []
        for r in result:
            evas = [
                r.evaluation_score_Q1,
                r.evaluation_score_Q2,
                r.evaluation_score_Q3,
                r.evaluation_score_Q4,
                r.evaluation_score_Q5,
                r.evaluation_score_Q6,
            ]
            cnt = 0
            for e, a in zip(evas, avgs):
                if e >= a:
                    cnt += 1
            outputs.append((cnt, sum(evas), r))

        outputs = sorted(outputs, key=lambda x: (x[0], x[1]), reverse=True)
        outputs = [r for _, _, r in outputs]

        return outputs[:limit]

    def get_materials(self, db: Session, job_id: int) -> List[JobMaterialsUploaded]:
        result = db.query(JobMaterialsUploaded).filter(JobMaterialsUploaded.job_id == job_id).all()

        return result


jobs = CRUDJobs(Jobs)
