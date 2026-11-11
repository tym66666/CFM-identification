"""Explicit synthetic binary-IV research problem and two separate review records."""
from cfm_id.iv_route_contract import (IVProblem,IVCell,IVReview,IVReadingReview,
    IVScienceReview,VERSION,READING_DECISIONS,SCIENCE_DECISIONS,digest)

OBS={(0,0,0):0.0,(0,0,1):1.0,(0,1,0):0.0,(0,1,1):0.0,
     (1,0,0):0.0,(1,0,1):0.75,(1,1,0):0.125,(1,1,1):0.125}

def make_problem():
    return IVProblem(version=VERSION,target='LATE',
        cells=[IVCell(z=z,d=d,y=y,probability=str(v)) for (z,d,y),v in OBS.items()],
        monotonicity=True,instrument='randomized offer',treatment='participation',outcome='binary outcome',
        population='Synthetic study population',context='Synthetic demonstration only',
        source_ids=['synthetic-table-1'],source_sha256='a'*64,
        assumptions=['instrument_independence','exclusion_restriction','monotonicity_direction','consistency_and_binary_outcome','no_interference','positive_instrument_support'])

def synthetic_review(problem):
    h=digest(problem)
    return IVReview(version=VERSION,problem_sha256=h,
        reading_review=IVReadingReview(authority='SYNTHETIC_TEST',reviewer='Synthetic reader',evidence='Synthetic fixture; all eight cells and variable coding checked.',problem_sha256=h,
            decisions={k:'ACCEPTED' for k in READING_DECISIONS}),
        science_review=IVScienceReview(authority='SYNTHETIC_TEST',reviewer='Synthetic reviewer',evidence='Synthetic-only declarations for the example; not external scientific evidence.',problem_sha256=h,
            decisions={k:'ACCEPTED' for k in SCIENCE_DECISIONS}))
