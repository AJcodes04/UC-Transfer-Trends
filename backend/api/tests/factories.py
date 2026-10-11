from api.models import TransferData


def make_transfer_data(**kwargs):
    """
    Shortcut to create a TransferData row with sensible defaults.
    Tests only need to specify the fields they care about.
    """
    defaults = {
        'university': 'UCB',
        'year': 2023,
        'broad_discipline': 'Sciences',
        'college_school': 'Letters & Science',
        'major_name': 'Test Major',
        'applicants': 100,
        'admits': 50,
        'enrolls': 25,
        'admit_rate': 50,
        'yield_rate': 50,
    }
    defaults.update(kwargs)
    return TransferData.objects.create(**defaults)
