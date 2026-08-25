import json
import os
from pathlib import Path
from app.catalog import load_catalog
from app.agent_contract import parse_analysis

catalog = load_catalog()

# 1. Bùi Nguyễn Hồng Giang
giang_data = {
    'schema_version': '1.0',
    'produced_by': 'antigravity-runtime-agent',
    'person_folder': 'Bùi Nguyễn Hồng Giang',
    'source_file': 'Tài liệu đảng viên.pdf',
    'page_count': 11,
    'pages': [
        {'page_number': 1, 'page_role': 'CONTENT', 'title_guess': 'Giấy chứng nhận bồi dưỡng QP&AN đối tượng 4', 'document_date': '2018-07-20', 'date_confidence': 0.99, 'type_candidates': ['86'], 'starts_new_document': True, 'continues_previous': False, 'attach_hint': 'NONE', 'notes': 'Chứng nhận QP&AN đối tượng 4'},
        {'page_number': 2, 'page_role': 'COVER', 'title_guess': 'Bìa Giấy chứng nhận QP&AN', 'document_date': None, 'date_confidence': 0.0, 'type_candidates': ['86'], 'starts_new_document': False, 'continues_previous': True, 'attach_hint': 'PREVIOUS', 'notes': 'Bìa đỏ của trang 1'},
        {'page_number': 3, 'page_role': 'CONTENT', 'title_guess': 'Giấy chứng nhận bồi dưỡng quy hoạch chức danh Phó Trưởng phòng', 'document_date': '2019-03-21', 'date_confidence': 0.99, 'type_candidates': ['86'], 'starts_new_document': True, 'continues_previous': False, 'attach_hint': 'NONE', 'notes': 'Chứng nhận lớp quy hoạch chức danh'},
        {'page_number': 4, 'page_role': 'COVER', 'title_guess': 'Bìa Giấy chứng chỉ Học viện ANND', 'document_date': None, 'date_confidence': 0.0, 'type_candidates': ['86'], 'starts_new_document': False, 'continues_previous': True, 'attach_hint': 'PREVIOUS', 'notes': 'Bìa đỏ của trang 3'},
        {'page_number': 5, 'page_role': 'CONTENT', 'title_guess': 'Chứng chỉ ứng dụng CNTT cơ bản', 'document_date': '2019-07-30', 'date_confidence': 0.99, 'type_candidates': ['86'], 'starts_new_document': True, 'continues_previous': False, 'attach_hint': 'NONE', 'notes': 'Chứng chỉ CNTT cơ bản'},
        {'page_number': 6, 'page_role': 'COVER', 'title_guess': 'Bìa Chứng chỉ ứng dụng CNTT cơ bản', 'document_date': None, 'date_confidence': 0.0, 'type_candidates': ['86'], 'starts_new_document': False, 'continues_previous': True, 'attach_hint': 'PREVIOUS', 'notes': 'Bìa đỏ của trang 5'},
        {'page_number': 7, 'page_role': 'CONTENT', 'title_guess': 'Quyết định điều động cán bộ', 'document_date': '2023-08-28', 'date_confidence': 0.99, 'type_candidates': ['87'], 'starts_new_document': True, 'continues_previous': False, 'attach_hint': 'NONE', 'notes': 'QĐ số 1602/QĐ-CAT-PX01'},
        {'page_number': 8, 'page_role': 'CONTENT', 'title_guess': 'Quyết định bố trí cán bộ', 'document_date': '2019-12-23', 'date_confidence': 0.99, 'type_candidates': ['87'], 'starts_new_document': True, 'continues_previous': False, 'attach_hint': 'NONE', 'notes': 'QĐ số 22/QĐ-CAT-PX01'},
        {'page_number': 9, 'page_role': 'CONTENT', 'title_guess': 'Quyết định bổ nhiệm cán bộ', 'document_date': '2009-08-14', 'date_confidence': 0.99, 'type_candidates': ['87'], 'starts_new_document': True, 'continues_previous': False, 'attach_hint': 'NONE', 'notes': 'QĐ số 634/QĐ-CAT(PX13)'},
        {'page_number': 10, 'page_role': 'CONTENT', 'title_guess': 'Quyết định bổ nhiệm cán bộ', 'document_date': '2007-02-12', 'date_confidence': 0.99, 'type_candidates': ['87'], 'starts_new_document': True, 'continues_previous': False, 'attach_hint': 'NONE', 'notes': 'QĐ số 78/QĐ-CAT(PX13)'},
        {'page_number': 11, 'page_role': 'CONTENT', 'title_guess': 'Quyết định luân chuyển cán bộ', 'document_date': '2017-05-25', 'date_confidence': 0.99, 'type_candidates': ['87'], 'starts_new_document': True, 'continues_previous': False, 'attach_hint': 'NONE', 'notes': 'QĐ số 612/QĐ-CAT-PX13'}
    ],
    'documents': [
        {'source_pages': [1, 2], 'type_id': '86', 'confidence': 0.98, 'document_date': '2018-07-20', 'date_confidence': 0.99, 'title_short': 'Chứng nhận Bồi dưỡng QP&AN đối tượng 4', 'needs_review': False, 'review_reason': None},
        {'source_pages': [3, 4], 'type_id': '86', 'confidence': 0.98, 'document_date': '2019-03-21', 'date_confidence': 0.99, 'title_short': 'Chứng nhận Bồi dưỡng chức danh Phó Trưởng phòng', 'needs_review': False, 'review_reason': None},
        {'source_pages': [5, 6], 'type_id': '86', 'confidence': 0.98, 'document_date': '2019-07-30', 'date_confidence': 0.99, 'title_short': 'Chứng chỉ CNTT cơ bản', 'needs_review': False, 'review_reason': None},
        {'source_pages': [7], 'type_id': '87', 'confidence': 0.99, 'document_date': '2023-08-28', 'date_confidence': 0.99, 'title_short': 'Quyết định điều động cán bộ số 1602', 'needs_review': False, 'review_reason': None},
        {'source_pages': [8], 'type_id': '87', 'confidence': 0.99, 'document_date': '2019-12-23', 'date_confidence': 0.99, 'title_short': 'Quyết định bố trí cán bộ số 22', 'needs_review': False, 'review_reason': None},
        {'source_pages': [9], 'type_id': '87', 'confidence': 0.99, 'document_date': '2009-08-14', 'date_confidence': 0.99, 'title_short': 'Quyết định bổ nhiệm cán bộ số 634', 'needs_review': False, 'review_reason': None},
        {'source_pages': [10], 'type_id': '87', 'confidence': 0.99, 'document_date': '2007-02-12', 'date_confidence': 0.99, 'title_short': 'Quyết định bổ nhiệm cán bộ số 78', 'needs_review': False, 'review_reason': None},
        {'source_pages': [11], 'type_id': '87', 'confidence': 0.99, 'document_date': '2017-05-25', 'date_confidence': 0.99, 'title_short': 'Quyết định luân chuyển cán bộ số 612', 'needs_review': False, 'review_reason': None}
    ]
}

# 2. Phan Văn Mạnh
manh_data = {
    'schema_version': '1.0',
    'produced_by': 'antigravity-runtime-agent',
    'person_folder': 'Phan Văn Mạnh',
    'source_file': 'SOCIALIST REPUBLIC OF VIETNAM.pdf',
    'page_count': 9,
    'pages': [
        {'page_number': 1, 'page_role': 'CONTENT', 'title_guess': 'Bằng cử nhân Luật', 'document_date': '2012-05-30', 'date_confidence': 0.99, 'type_candidates': ['86'], 'starts_new_document': True, 'continues_previous': False, 'attach_hint': 'NONE', 'notes': 'Bằng ĐH ANND'},
        {'page_number': 2, 'page_role': 'CONTENT', 'title_guess': 'Chứng nhận tốt nghiệp hoàn thiện Trung cấp LLCT', 'document_date': '2017-12-18', 'date_confidence': 0.99, 'type_candidates': ['70'], 'starts_new_document': True, 'continues_previous': False, 'attach_hint': 'NONE', 'notes': 'Chứng nhận LLCT'},
        {'page_number': 3, 'page_role': 'CONTENT', 'title_guess': 'Chứng nhận Bồi dưỡng QP&AN đối tượng 4', 'document_date': '2018-09-21', 'date_confidence': 0.99, 'type_candidates': ['86'], 'starts_new_document': True, 'continues_previous': False, 'attach_hint': 'NONE', 'notes': 'Chứng nhận QP&AN'},
        {'page_number': 4, 'page_role': 'CONTENT', 'title_guess': 'Chứng chỉ CNTT cơ bản', 'document_date': '2018-06-09', 'date_confidence': 0.99, 'type_candidates': ['86'], 'starts_new_document': True, 'continues_previous': False, 'attach_hint': 'NONE', 'notes': 'Chứng chỉ CNTT'},
        {'page_number': 5, 'page_role': 'CONTENT', 'title_guess': 'Giấy khai sinh bản sao', 'document_date': '1988-10-30', 'date_confidence': 0.95, 'type_candidates': ['75'], 'starts_new_document': True, 'continues_previous': False, 'attach_hint': 'NONE', 'notes': 'Bản sao GKS'},
        {'page_number': 6, 'page_role': 'CONTENT', 'title_guess': 'Giấy khai sinh bản sao bản 2', 'document_date': '1988-10-30', 'date_confidence': 0.95, 'type_candidates': ['75'], 'starts_new_document': True, 'continues_previous': False, 'attach_hint': 'NONE', 'notes': 'Bản sao GKS thứ 2'},
        {'page_number': 7, 'page_role': 'CONTENT', 'title_guess': 'Quyết định bổ nhiệm chức danh Trinh sát viên', 'document_date': '2018-05-21', 'date_confidence': 0.99, 'type_candidates': ['87'], 'starts_new_document': True, 'continues_previous': False, 'attach_hint': 'NONE', 'notes': 'QĐ số 598/QĐ-CAT-PX13'},
        {'page_number': 8, 'page_role': 'CONTENT', 'title_guess': 'Quyết định bố trí cán bộ', 'document_date': '2025-06-25', 'date_confidence': 0.99, 'type_candidates': ['87'], 'starts_new_document': True, 'continues_previous': False, 'attach_hint': 'NONE', 'notes': 'QĐ số 4561/QĐ-CAT-PX01'},
        {'page_number': 9, 'page_role': 'CONTENT', 'title_guess': 'Quyết định điều động cán bộ', 'document_date': '2012-06-12', 'date_confidence': 0.99, 'type_candidates': ['87'], 'starts_new_document': True, 'continues_previous': False, 'attach_hint': 'NONE', 'notes': 'QĐ số 833/QĐ-CAT(PX13)'}
    ],
    'documents': [
        {'source_pages': [1], 'type_id': '86', 'confidence': 0.99, 'document_date': '2012-05-30', 'date_confidence': 0.99, 'title_short': 'Bằng cử nhân Luật', 'needs_review': False, 'review_reason': None},
        {'source_pages': [2], 'type_id': '70', 'confidence': 0.99, 'document_date': '2017-12-18', 'date_confidence': 0.99, 'title_short': 'Chứng nhận hoàn thiện Trung cấp LLCT', 'needs_review': False, 'review_reason': None},
        {'source_pages': [3], 'type_id': '86', 'confidence': 0.99, 'document_date': '2018-09-21', 'date_confidence': 0.99, 'title_short': 'Chứng nhận Bồi dưỡng QP&AN đối tượng 4', 'needs_review': False, 'review_reason': None},
        {'source_pages': [4], 'type_id': '86', 'confidence': 0.99, 'document_date': '2018-06-09', 'date_confidence': 0.99, 'title_short': 'Chứng chỉ CNTT cơ bản', 'needs_review': False, 'review_reason': None},
        {'source_pages': [5], 'type_id': '75', 'confidence': 0.99, 'document_date': '1988-10-30', 'date_confidence': 0.95, 'title_short': 'Giấy khai sinh bản sao 1', 'needs_review': False, 'review_reason': None},
        {'source_pages': [6], 'type_id': '75', 'confidence': 0.99, 'document_date': '1988-10-30', 'date_confidence': 0.95, 'title_short': 'Giấy khai sinh bản sao 2', 'needs_review': False, 'review_reason': None},
        {'source_pages': [7], 'type_id': '87', 'confidence': 0.99, 'document_date': '2018-05-21', 'date_confidence': 0.99, 'title_short': 'Quyết định bổ nhiệm TSV trung cấp số 598', 'needs_review': False, 'review_reason': None},
        {'source_pages': [8], 'type_id': '87', 'confidence': 0.99, 'document_date': '2025-06-25', 'date_confidence': 0.99, 'title_short': 'Quyết định bố trí cán bộ số 4561', 'needs_review': False, 'review_reason': None},
        {'source_pages': [9], 'type_id': '87', 'confidence': 0.99, 'document_date': '2012-06-12', 'date_confidence': 0.99, 'title_short': 'Quyết định điều động cán bộ số 833', 'needs_review': False, 'review_reason': None}
    ]
}

# 3. Trương Tuấn Thanh
thanh_data = {
    'schema_version': '1.0',
    'produced_by': 'antigravity-runtime-agent',
    'person_folder': 'Trương Tuấn Thanh',
    'source_file': 'Truongtuanthanh.pdf',
    'page_count': 17,
    'pages': [
        {'page_number': 1, 'page_role': 'CONTENT', 'title_guess': 'Quyết định điều động cán bộ', 'document_date': '2020-01-09', 'date_confidence': 0.99, 'type_candidates': ['87'], 'starts_new_document': True, 'continues_previous': False, 'attach_hint': 'NONE', 'notes': 'QĐ số 69/QĐ-CAT-PX01'},
        {'page_number': 2, 'page_role': 'CONTENT', 'title_guess': 'Quyết định bố trí cán bộ', 'document_date': '2025-06-25', 'date_confidence': 0.99, 'type_candidates': ['87'], 'starts_new_document': True, 'continues_previous': False, 'attach_hint': 'NONE', 'notes': 'QĐ số 4599/QĐ-CAT-PX01'},
        {'page_number': 3, 'page_role': 'CONTENT', 'title_guess': 'Chứng nhận bồi dưỡng Chuyển đổi số', 'document_date': '2025-11-28', 'date_confidence': 0.99, 'type_candidates': ['86'], 'starts_new_document': True, 'continues_previous': False, 'attach_hint': 'NONE', 'notes': 'Chứng nhận Chuyển đổi số'},
        {'page_number': 4, 'page_role': 'CONTENT', 'title_guess': 'Chứng nhận bồi dưỡng QP&AN đối tượng 4', 'document_date': '2018-11-16', 'date_confidence': 0.99, 'type_candidates': ['86'], 'starts_new_document': True, 'continues_previous': False, 'attach_hint': 'NONE', 'notes': 'Chứng nhận QP&AN'},
        {'page_number': 5, 'page_role': 'CONTENT', 'title_guess': 'Bản chính Giấy khai sinh', 'document_date': '1979-08-02', 'date_confidence': 0.95, 'type_candidates': ['75'], 'starts_new_document': True, 'continues_previous': False, 'attach_hint': 'NONE', 'notes': 'Bản chính GKS'},
        {'page_number': 6, 'page_role': 'CONTENT', 'title_guess': 'Giấy xác nhận trình độ LLCT tương đương Trung cấp', 'document_date': '2020-06-08', 'date_confidence': 0.99, 'type_candidates': ['70'], 'starts_new_document': True, 'continues_previous': False, 'attach_hint': 'NONE', 'notes': 'Xác nhận LLCT'},
        {'page_number': 7, 'page_role': 'CONTENT', 'title_guess': 'Bằng tốt nghiệp Đại học Cử nhân Luật', 'document_date': '2002-09-17', 'date_confidence': 0.99, 'type_candidates': ['86'], 'starts_new_document': True, 'continues_previous': False, 'attach_hint': 'NONE', 'notes': 'Bằng ĐH ANND'},
        {'page_number': 8, 'page_role': 'CONTENT', 'title_guess': 'Chứng chỉ Tin học ứng dụng trình độ A', 'document_date': '2009-06-15', 'date_confidence': 0.99, 'type_candidates': ['86'], 'starts_new_document': True, 'continues_previous': False, 'attach_hint': 'NONE', 'notes': 'Chứng chỉ Tin học A'},
        {'page_number': 9, 'page_role': 'CONTENT', 'title_guess': 'Chứng chỉ Môn học Thể dục', 'document_date': '1998-12-09', 'date_confidence': 0.99, 'type_candidates': ['86'], 'starts_new_document': True, 'continues_previous': False, 'attach_hint': 'NONE', 'notes': 'Chứng chỉ Thể dục ĐH ANND'},
        {'page_number': 10, 'page_role': 'CONTENT', 'title_guess': 'Chứng chỉ Quản lý vũ khí', 'document_date': '2017-10-26', 'date_confidence': 0.99, 'type_candidates': ['86'], 'starts_new_document': True, 'continues_previous': False, 'attach_hint': 'NONE', 'notes': 'Chứng chỉ Quản lý vũ khí'},
        {'page_number': 11, 'page_role': 'CONTENT', 'title_guess': 'Bằng tốt nghiệp Phổ thông cơ sở', 'document_date': '1994-09-01', 'date_confidence': 0.99, 'type_candidates': ['86'], 'starts_new_document': True, 'continues_previous': False, 'attach_hint': 'NONE', 'notes': 'Bằng THCS'},
        {'page_number': 12, 'page_role': 'CONTENT', 'title_guess': 'Chứng nhận Bồi dưỡng CACQ đảm nhiệm chức danh CAX', 'document_date': '2019-11-21', 'date_confidence': 0.99, 'type_candidates': ['86'], 'starts_new_document': True, 'continues_previous': False, 'attach_hint': 'NONE', 'notes': 'Chứng nhận CĐ ANND I'},
        {'page_number': 13, 'page_role': 'CONTENT', 'title_guess': 'Chứng chỉ Quản lý công cụ hỗ trợ', 'document_date': '2017-10-26', 'date_confidence': 0.99, 'type_candidates': ['86'], 'starts_new_document': True, 'continues_previous': False, 'attach_hint': 'NONE', 'notes': 'Chứng chỉ Quản lý CCHT'},
        {'page_number': 14, 'page_role': 'CONTENT', 'title_guess': 'Chứng chỉ Tiếng Anh trình độ B', 'document_date': '2011-01-24', 'date_confidence': 0.99, 'type_candidates': ['86'], 'starts_new_document': True, 'continues_previous': False, 'attach_hint': 'NONE', 'notes': 'Chứng chỉ Tiếng Anh B'},
        {'page_number': 15, 'page_role': 'CONTENT', 'title_guess': 'Chứng chỉ CNTT cơ bản', 'document_date': '2017-09-12', 'date_confidence': 0.99, 'type_candidates': ['86'], 'starts_new_document': True, 'continues_previous': False, 'attach_hint': 'NONE', 'notes': 'Chứng chỉ CNTT'},
        {'page_number': 16, 'page_role': 'CONTENT', 'title_guess': 'Chứng chỉ Tiếng Anh trình độ A', 'document_date': '2010-09-15', 'date_confidence': 0.99, 'type_candidates': ['86'], 'starts_new_document': True, 'continues_previous': False, 'attach_hint': 'NONE', 'notes': 'Chứng chỉ Tiếng Anh A'},
        {'page_number': 17, 'page_role': 'CONTENT', 'title_guess': 'Bằng Tú tài Phổ thông trung học', 'document_date': '1997-12-01', 'date_confidence': 0.99, 'type_candidates': ['86'], 'starts_new_document': True, 'continues_previous': False, 'attach_hint': 'NONE', 'notes': 'Bằng THPT'}
    ],
    'documents': [
        {'source_pages': [1], 'type_id': '87', 'confidence': 0.99, 'document_date': '2020-01-09', 'date_confidence': 0.99, 'title_short': 'Quyết định điều động cán bộ số 69', 'needs_review': False, 'review_reason': None},
        {'source_pages': [2], 'type_id': '87', 'confidence': 0.99, 'document_date': '2025-06-25', 'date_confidence': 0.99, 'title_short': 'Quyết định bố trí cán bộ số 4599', 'needs_review': False, 'review_reason': None},
        {'source_pages': [3], 'type_id': '86', 'confidence': 0.99, 'document_date': '2025-11-28', 'date_confidence': 0.99, 'title_short': 'Chứng nhận Bồi dưỡng chuyển đổi số', 'needs_review': False, 'review_reason': None},
        {'source_pages': [4], 'type_id': '86', 'confidence': 0.99, 'document_date': '2018-11-16', 'date_confidence': 0.99, 'title_short': 'Chứng nhận Bồi dưỡng QP&AN đối tượng 4', 'needs_review': False, 'review_reason': None},
        {'source_pages': [5], 'type_id': '75', 'confidence': 0.99, 'document_date': '1979-08-02', 'date_confidence': 0.95, 'title_short': 'Bản chính Giấy khai sinh', 'needs_review': False, 'review_reason': None},
        {'source_pages': [6], 'type_id': '70', 'confidence': 0.99, 'document_date': '2020-06-08', 'date_confidence': 0.99, 'title_short': 'Giấy xác nhận trình độ LLCT tương đương Trung cấp', 'needs_review': False, 'review_reason': None},
        {'source_pages': [7], 'type_id': '86', 'confidence': 0.99, 'document_date': '2002-09-17', 'date_confidence': 0.99, 'title_short': 'Bằng tốt nghiệp ĐH Cử nhân Luật', 'needs_review': False, 'review_reason': None},
        {'source_pages': [8], 'type_id': '86', 'confidence': 0.99, 'document_date': '2009-06-15', 'date_confidence': 0.99, 'title_short': 'Chứng chỉ Tin học trình độ A', 'needs_review': False, 'review_reason': None},
        {'source_pages': [9], 'type_id': '86', 'confidence': 0.99, 'document_date': '1998-12-09', 'date_confidence': 0.99, 'title_short': 'Chứng chỉ Môn học Thể dục', 'needs_review': False, 'review_reason': None},
        {'source_pages': [10], 'type_id': '86', 'confidence': 0.99, 'document_date': '2017-10-26', 'date_confidence': 0.99, 'title_short': 'Chứng chỉ Quản lý vũ khí', 'needs_review': False, 'review_reason': None},
        {'source_pages': [11], 'type_id': '86', 'confidence': 0.99, 'document_date': '1994-09-01', 'date_confidence': 0.99, 'title_short': 'Bằng tốt nghiệp Phổ thông cơ sở', 'needs_review': False, 'review_reason': None},
        {'source_pages': [12], 'type_id': '86', 'confidence': 0.99, 'document_date': '2019-11-21', 'date_confidence': 0.99, 'title_short': 'Chứng nhận Bồi dưỡng CACQ đảm nhiệm CAX', 'needs_review': False, 'review_reason': None},
        {'source_pages': [13], 'type_id': '86', 'confidence': 0.99, 'document_date': '2017-10-26', 'date_confidence': 0.99, 'title_short': 'Chứng chỉ Quản lý công cụ hỗ trợ', 'needs_review': False, 'review_reason': None},
        {'source_pages': [14], 'type_id': '86', 'confidence': 0.99, 'document_date': '2011-01-24', 'date_confidence': 0.99, 'title_short': 'Chứng chỉ Tiếng Anh trình độ B', 'needs_review': False, 'review_reason': None},
        {'source_pages': [15], 'type_id': '86', 'confidence': 0.99, 'document_date': '2017-09-12', 'date_confidence': 0.99, 'title_short': 'Chứng chỉ CNTT cơ bản', 'needs_review': False, 'review_reason': None},
        {'source_pages': [16], 'type_id': '86', 'confidence': 0.99, 'document_date': '2010-09-15', 'date_confidence': 0.99, 'title_short': 'Chứng chỉ Tiếng Anh trình độ A', 'needs_review': False, 'review_reason': None},
        {'source_pages': [17], 'type_id': '86', 'confidence': 0.99, 'document_date': '1997-12-01', 'date_confidence': 0.99, 'title_short': 'Bằng Tú tài PTTH', 'needs_review': False, 'review_reason': None}
    ]
}

# 4. Hoàng Thị Kim Anh (4 files)
kim_anh_0308 = {
    'schema_version': '1.0',
    'produced_by': 'antigravity-runtime-agent',
    'person_folder': 'Hoàng Thị Kim Anh',
    'source_file': 'Color0308.pdf',
    'page_count': 23,
    'pages': [
        {'page_number': 1, 'page_role': 'CONTENT', 'title_guess': 'Giấy khai sinh bản chính', 'document_date': '1988-04-24', 'date_confidence': 0.95, 'type_candidates': ['75'], 'starts_new_document': True, 'continues_previous': False, 'attach_hint': 'NONE', 'notes': 'Mặt trước GKS'},
        {'page_number': 2, 'page_role': 'BACK_SIDE', 'title_guess': 'Mặt sau Giấy khai sinh', 'document_date': None, 'date_confidence': 0.0, 'type_candidates': ['75'], 'starts_new_document': False, 'continues_previous': True, 'attach_hint': 'PREVIOUS', 'notes': 'Mặt sau GKS'},
        {'page_number': 3, 'page_role': 'CONTENT', 'title_guess': 'Quyết định tạm tuyển cán bộ', 'document_date': '2013-10-10', 'date_confidence': 0.99, 'type_candidates': ['87'], 'starts_new_document': True, 'continues_previous': False, 'attach_hint': 'NONE', 'notes': 'QĐ số 1330/QĐ-CAT(PX13)'},
        {'page_number': 4, 'page_role': 'BLANK', 'title_guess': 'Mặt sau Quyết định tạm tuyển cán bộ', 'document_date': None, 'date_confidence': 0.0, 'type_candidates': ['87'], 'starts_new_document': False, 'continues_previous': True, 'attach_hint': 'PREVIOUS', 'notes': 'Mặt sau trắng'},
        {'page_number': 5, 'page_role': 'CONTENT', 'title_guess': 'Quyết định tuyển chính thức vào CAND', 'document_date': '2014-05-07', 'date_confidence': 0.99, 'type_candidates': ['87'], 'starts_new_document': True, 'continues_previous': False, 'attach_hint': 'NONE', 'notes': 'QĐ số 672/QĐ-CAT(PX13)'},
        {'page_number': 6, 'page_role': 'CONTENT', 'title_guess': 'Quyết định thăng cấp bậc hàm Thiếu úy lên Trung úy', 'document_date': '2016-05-31', 'date_confidence': 0.99, 'type_candidates': ['87'], 'starts_new_document': True, 'continues_previous': False, 'attach_hint': 'NONE', 'notes': 'QĐ số 842/QĐ-CAT-PX13'},
        {'page_number': 7, 'page_role': 'CONTENT', 'title_guess': 'Quyết định kết nạp đảng viên', 'document_date': '2016-10-27', 'date_confidence': 0.99, 'type_candidates': ['05'], 'starts_new_document': True, 'continues_previous': False, 'attach_hint': 'NONE', 'notes': 'QĐ số 336-QĐ/ĐUCA'},
        {'page_number': 8, 'page_role': 'CONTENT', 'title_guess': 'Quyết định công nhận đảng viên chính thức', 'document_date': '2017-12-21', 'date_confidence': 0.99, 'type_candidates': ['06'], 'starts_new_document': True, 'continues_previous': False, 'attach_hint': 'NONE', 'notes': 'QĐ số 619-QĐ/ĐUCA'},
        {'page_number': 9, 'page_role': 'CONTENT', 'title_guess': 'Quyết định thăng cấp bậc hàm Trung úy lên Thượng úy', 'document_date': '2019-05-20', 'date_confidence': 0.99, 'type_candidates': ['87'], 'starts_new_document': True, 'continues_previous': False, 'attach_hint': 'NONE', 'notes': 'QĐ số 838/QĐ-CAT-PX01'},
        {'page_number': 10, 'page_role': 'CONTENT', 'title_guess': 'Chứng nhận bổ sung kiến thức tương đương Trung cấp LLCT', 'document_date': '2020-03-02', 'date_confidence': 0.99, 'type_candidates': ['70'], 'starts_new_document': True, 'continues_previous': False, 'attach_hint': 'NONE', 'notes': 'Chứng nhận LLCT HV ANND'},
        {'page_number': 11, 'page_role': 'COVER', 'title_guess': 'Bìa Chứng nhận LLCT', 'document_date': None, 'date_confidence': 0.0, 'type_candidates': ['70'], 'starts_new_document': False, 'continues_previous': True, 'attach_hint': 'PREVIOUS', 'notes': 'Bìa đỏ của trang 10'},
        {'page_number': 12, 'page_role': 'CONTENT', 'title_guess': 'Chứng nhận Bồi dưỡng QP&AN đối tượng 4', 'document_date': '2019-09-20', 'date_confidence': 0.99, 'type_candidates': ['86'], 'starts_new_document': True, 'continues_previous': False, 'attach_hint': 'NONE', 'notes': 'Chứng nhận QP&AN'},
        {'page_number': 13, 'page_role': 'COVER', 'title_guess': 'Bìa Chứng nhận QP&AN', 'document_date': None, 'date_confidence': 0.0, 'type_candidates': ['86'], 'starts_new_document': False, 'continues_previous': True, 'attach_hint': 'PREVIOUS', 'notes': 'Bìa đỏ của trang 12'},
        {'page_number': 14, 'page_role': 'CONTENT', 'title_guess': 'Quyết định điều động cán bộ', 'document_date': '2021-08-05', 'date_confidence': 0.99, 'type_candidates': ['87'], 'starts_new_document': True, 'continues_previous': False, 'attach_hint': 'NONE', 'notes': 'QĐ số 1343/QĐ-CAT-PX01'},
        {'page_number': 15, 'page_role': 'CONTENT', 'title_guess': 'Quyết định thăng cấp bậc hàm Thượng úy lên Đại úy', 'document_date': '2022-05-19', 'date_confidence': 0.99, 'type_candidates': ['87'], 'starts_new_document': True, 'continues_previous': False, 'attach_hint': 'NONE', 'notes': 'QĐ số 706/QĐ-CAT-PX01'},
        {'page_number': 16, 'page_role': 'CONTENT', 'title_guess': 'Quyết định cử cán bộ đi học', 'document_date': '2023-05-12', 'date_confidence': 0.99, 'type_candidates': ['87'], 'starts_new_document': True, 'continues_previous': False, 'attach_hint': 'NONE', 'notes': 'QĐ số 787/QĐ-CAT-PX01'},
        {'page_number': 17, 'page_role': 'CONTENT', 'title_guess': 'Bằng cử nhân Cảnh sát nhân dân', 'document_date': '2025-06-05', 'date_confidence': 0.99, 'type_candidates': ['86'], 'starts_new_document': True, 'continues_previous': False, 'attach_hint': 'NONE', 'notes': 'Bằng VB2 CSND'},
        {'page_number': 18, 'page_role': 'COVER', 'title_guess': 'Bìa Bằng Cử nhân', 'document_date': None, 'date_confidence': 0.0, 'type_candidates': ['86'], 'starts_new_document': False, 'continues_previous': True, 'attach_hint': 'PREVIOUS', 'notes': 'Bìa đỏ của trang 17'},
        {'page_number': 19, 'page_role': 'CONTENT', 'title_guess': 'Quyết định điều động đối với học viên', 'document_date': '2025-07-07', 'date_confidence': 0.99, 'type_candidates': ['87'], 'starts_new_document': True, 'continues_previous': False, 'attach_hint': 'NONE', 'notes': 'QĐ số 14272/QĐ-X01'},
        {'page_number': 20, 'page_role': 'CONTENT', 'title_guess': 'Quyết định điều động học viên tốt nghiệp ra trường', 'document_date': '2025-08-01', 'date_confidence': 0.99, 'type_candidates': ['87'], 'starts_new_document': True, 'continues_previous': False, 'attach_hint': 'NONE', 'notes': 'QĐ số 1150/QĐ-CAT-PX01'},
        {'page_number': 21, 'page_role': 'CONTENT', 'title_guess': 'Chứng nhận Bồi dưỡng kiến thức dân tộc đối tượng 4', 'document_date': '2025-12-12', 'date_confidence': 0.99, 'type_candidates': ['86'], 'starts_new_document': True, 'continues_previous': False, 'attach_hint': 'NONE', 'notes': 'Chứng nhận kiến thức dân tộc'},
        {'page_number': 22, 'page_role': 'COVER', 'title_guess': 'Bìa Chứng chỉ', 'document_date': None, 'date_confidence': 0.0, 'type_candidates': ['86'], 'starts_new_document': False, 'continues_previous': True, 'attach_hint': 'PREVIOUS', 'notes': 'Bìa đỏ của trang 21'},
        {'page_number': 23, 'page_role': 'CONTENT', 'title_guess': 'Quyết định thăng cấp bậc hàm Đại úy lên Thiếu tá', 'document_date': '2026-05-21', 'date_confidence': 0.99, 'type_candidates': ['87'], 'starts_new_document': True, 'continues_previous': False, 'attach_hint': 'NONE', 'notes': 'QĐ số 3979/QĐ-CAT-PX01'}
    ],
    'documents': [
        {'source_pages': [1, 2], 'type_id': '75', 'confidence': 0.99, 'document_date': '1988-04-24', 'date_confidence': 0.95, 'title_short': 'Giấy khai sinh bản chính', 'needs_review': False, 'review_reason': None},
        {'source_pages': [3, 4], 'type_id': '87', 'confidence': 0.99, 'document_date': '2013-10-10', 'date_confidence': 0.99, 'title_short': 'Quyết định tạm tuyển cán bộ số 1330', 'needs_review': False, 'review_reason': None},
        {'source_pages': [5], 'type_id': '87', 'confidence': 0.99, 'document_date': '2014-05-07', 'date_confidence': 0.99, 'title_short': 'Quyết định tuyển chính thức số 672', 'needs_review': False, 'review_reason': None},
        {'source_pages': [6], 'type_id': '87', 'confidence': 0.99, 'document_date': '2016-05-31', 'date_confidence': 0.99, 'title_short': 'Quyết định thăng cấp Thiếu úy lên Trung úy số 842', 'needs_review': False, 'review_reason': None},
        {'source_pages': [7], 'type_id': '05', 'confidence': 0.99, 'document_date': '2016-10-27', 'date_confidence': 0.99, 'title_short': 'Quyết định kết nạp đảng viên số 336', 'needs_review': False, 'review_reason': None},
        {'source_pages': [8], 'type_id': '06', 'confidence': 0.99, 'document_date': '2017-12-21', 'date_confidence': 0.99, 'title_short': 'Quyết định công nhận đảng viên chính thức số 619', 'needs_review': False, 'review_reason': None},
        {'source_pages': [9], 'type_id': '87', 'confidence': 0.99, 'document_date': '2019-05-20', 'date_confidence': 0.99, 'title_short': 'Quyết định thăng cấp Trung úy lên Thượng úy số 838', 'needs_review': False, 'review_reason': None},
        {'source_pages': [10, 11], 'type_id': '70', 'confidence': 0.99, 'document_date': '2020-03-02', 'date_confidence': 0.99, 'title_short': 'Chứng nhận hoàn thiện Trung cấp LLCT', 'needs_review': False, 'review_reason': None},
        {'source_pages': [12, 13], 'type_id': '86', 'confidence': 0.99, 'document_date': '2019-09-20', 'date_confidence': 0.99, 'title_short': 'Chứng nhận Bồi dưỡng QP&AN đối tượng 4', 'needs_review': False, 'review_reason': None},
        {'source_pages': [14], 'type_id': '87', 'confidence': 0.99, 'document_date': '2021-08-05', 'date_confidence': 0.99, 'title_short': 'Quyết định điều động cán bộ số 1343', 'needs_review': False, 'review_reason': None},
        {'source_pages': [15], 'type_id': '87', 'confidence': 0.99, 'document_date': '2022-05-19', 'date_confidence': 0.99, 'title_short': 'Quyết định thăng cấp Thượng úy lên Đại úy số 706', 'needs_review': False, 'review_reason': None},
        {'source_pages': [16], 'type_id': '87', 'confidence': 0.99, 'document_date': '2023-05-12', 'date_confidence': 0.99, 'title_short': 'Quyết định cử cán bộ đi học số 787', 'needs_review': False, 'review_reason': None},
        {'source_pages': [17, 18], 'type_id': '86', 'confidence': 0.99, 'document_date': '2025-06-05', 'date_confidence': 0.99, 'title_short': 'Bằng cử nhân CSND', 'needs_review': False, 'review_reason': None},
        {'source_pages': [19], 'type_id': '87', 'confidence': 0.99, 'document_date': '2025-07-07', 'date_confidence': 0.99, 'title_short': 'Quyết định điều động học viên tốt nghiệp số 14272', 'needs_review': False, 'review_reason': None},
        {'source_pages': [20], 'type_id': '87', 'confidence': 0.99, 'document_date': '2025-08-01', 'date_confidence': 0.99, 'title_short': 'Quyết định điều động học viên về đơn vị số 1150', 'needs_review': False, 'review_reason': None},
        {'source_pages': [21, 22], 'type_id': '86', 'confidence': 0.99, 'document_date': '2025-12-12', 'date_confidence': 0.99, 'title_short': 'Chứng nhận Bồi dưỡng kiến thức dân tộc đối tượng 4', 'needs_review': False, 'review_reason': None},
        {'source_pages': [23], 'type_id': '87', 'confidence': 0.99, 'document_date': '2026-05-21', 'date_confidence': 0.99, 'title_short': 'Quyết định thăng cấp Đại úy lên Thiếu tá số 3979', 'needs_review': False, 'review_reason': None}
    ]
}

kim_anh_0309 = {
    'schema_version': '1.0',
    'produced_by': 'antigravity-runtime-agent',
    'person_folder': 'Hoàng Thị Kim Anh',
    'source_file': 'Color0309.pdf',
    'page_count': 2,
    'pages': [
        {'page_number': 1, 'page_role': 'CONTENT', 'title_guess': 'Bằng tốt nghiệp đại học Nông Lâm Thái Nguyên', 'document_date': '2010-08-04', 'date_confidence': 0.99, 'type_candidates': ['86'], 'starts_new_document': True, 'continues_previous': False, 'attach_hint': 'NONE', 'notes': 'Bằng ĐH Thái Nguyên'},
        {'page_number': 2, 'page_role': 'COVER', 'title_guess': 'Bìa Bằng tốt nghiệp Đại học', 'document_date': None, 'date_confidence': 0.0, 'type_candidates': ['86'], 'starts_new_document': False, 'continues_previous': True, 'attach_hint': 'PREVIOUS', 'notes': 'Bìa đỏ của trang 1'}
    ],
    'documents': [
        {'source_pages': [1, 2], 'type_id': '86', 'confidence': 0.99, 'document_date': '2010-08-04', 'date_confidence': 0.99, 'title_short': 'Bằng tốt nghiệp ĐH Nông Lâm Thái Nguyên', 'needs_review': False, 'review_reason': None}
    ]
}

kim_anh_0310 = {
    'schema_version': '1.0',
    'produced_by': 'antigravity-runtime-agent',
    'person_folder': 'Hoàng Thị Kim Anh',
    'source_file': 'Color0310.pdf',
    'page_count': 2,
    'pages': [
        {'page_number': 1, 'page_role': 'CONTENT', 'title_guess': 'Bằng tốt nghiệp trung học phổ thông', 'document_date': '2005-08-19', 'date_confidence': 0.99, 'type_candidates': ['86'], 'starts_new_document': True, 'continues_previous': False, 'attach_hint': 'NONE', 'notes': 'Bằng THPT'},
        {'page_number': 2, 'page_role': 'COVER', 'title_guess': 'Bìa Bằng tốt nghiệp trung học phổ thông', 'document_date': None, 'date_confidence': 0.0, 'type_candidates': ['86'], 'starts_new_document': False, 'continues_previous': True, 'attach_hint': 'PREVIOUS', 'notes': 'Bìa của trang 1'}
    ],
    'documents': [
        {'source_pages': [1, 2], 'type_id': '86', 'confidence': 0.99, 'document_date': '2005-08-19', 'date_confidence': 0.99, 'title_short': 'Bằng tốt nghiệp THPT', 'needs_review': False, 'review_reason': None}
    ]
}

kim_anh_0311 = {
    'schema_version': '1.0',
    'produced_by': 'antigravity-runtime-agent',
    'person_folder': 'Hoàng Thị Kim Anh',
    'source_file': 'Color0311.pdf',
    'page_count': 4,
    'pages': [
        {'page_number': 1, 'page_role': 'CONTENT', 'title_guess': 'Chứng chỉ ứng dụng CNTT cơ bản', 'document_date': '2020-12-31', 'date_confidence': 0.99, 'type_candidates': ['86'], 'starts_new_document': True, 'continues_previous': False, 'attach_hint': 'NONE', 'notes': 'Chứng chỉ CNTT'},
        {'page_number': 2, 'page_role': 'COVER', 'title_guess': 'Bìa Chứng chỉ ứng dụng CNTT cơ bản', 'document_date': None, 'date_confidence': 0.0, 'type_candidates': ['86'], 'starts_new_document': False, 'continues_previous': True, 'attach_hint': 'PREVIOUS', 'notes': 'Bìa đỏ của trang 1'},
        {'page_number': 3, 'page_role': 'CONTENT', 'title_guess': 'Chứng nhận Huấn luyện Điều lệnh Quân sự Võ thuật năm 2014', 'document_date': '2014-09-23', 'date_confidence': 0.99, 'type_candidates': ['86'], 'starts_new_document': True, 'continues_previous': False, 'attach_hint': 'NONE', 'notes': 'Chứng nhận Điều lệnh võ thuật'},
        {'page_number': 4, 'page_role': 'COVER', 'title_guess': 'Bìa Chứng chỉ Huấn luyện Điều lệnh', 'document_date': None, 'date_confidence': 0.0, 'type_candidates': ['86'], 'starts_new_document': False, 'continues_previous': True, 'attach_hint': 'PREVIOUS', 'notes': 'Bìa đỏ của trang 3'}
    ],
    'documents': [
        {'source_pages': [1, 2], 'type_id': '86', 'confidence': 0.99, 'document_date': '2020-12-31', 'date_confidence': 0.99, 'title_short': 'Chứng chỉ CNTT cơ bản', 'needs_review': False, 'review_reason': None},
        {'source_pages': [3, 4], 'type_id': '86', 'confidence': 0.99, 'document_date': '2014-09-23', 'date_confidence': 0.99, 'title_short': 'Chứng nhận Huấn luyện Điều lệnh Võ thuật 2014', 'needs_review': False, 'review_reason': None}
    ]
}

all_payloads = [
    ('Bùi Nguyễn Hồng Giang', 'Tài liệu đảng viên.json', giang_data),
    ('Phan Văn Mạnh', 'SOCIALIST REPUBLIC OF VIETNAM.json', manh_data),
    ('Trương Tuấn Thanh', 'Truongtuanthanh.json', thanh_data),
    ('Hoàng Thị Kim Anh', 'Color0308.json', kim_anh_0308),
    ('Hoàng Thị Kim Anh', 'Color0309.json', kim_anh_0309),
    ('Hoàng Thị Kim Anh', 'Color0310.json', kim_anh_0310),
    ('Hoàng Thị Kim Anh', 'Color0311.json', kim_anh_0311)
]

for folder, fname, payload in all_payloads:
    for p in payload['pages']:
        if p.get('type_candidates'):
            new_tc = []
            for tc in p['type_candidates']:
                if isinstance(tc, str):
                    new_tc.append({'type_id': tc, 'confidence': 0.98})
                else:
                    new_tc.append(tc)
            p['type_candidates'] = new_tc
    raw_str = json.dumps(payload, ensure_ascii=False, indent=2)
    try:
        parsed = parse_analysis(raw_str, catalog, where=f"{folder}/{fname}")
        out_dir = Path('analysis') / folder
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / fname
        with open(out_file, 'w', encoding='utf-8') as f:
            f.write(raw_str)
        print(f'Successfully wrote & validated: {out_file}')
    except Exception as e:
        print(f'ERROR validating {folder}/{fname}: {e}')
