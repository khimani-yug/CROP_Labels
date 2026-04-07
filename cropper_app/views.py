from django.shortcuts import render
from django.http import HttpResponse, FileResponse
import fitz
import os
import uuid
import re
from datetime import date
from django.conf import settings

# Strictly match 'order__' followed by exactly 10 to 20 digits only
ORDER_PATTERN = re.compile(r'^order__\d{10,20}\.pdf$', re.IGNORECASE)

# Configuration
A4_W, A4_H = 595, 842
CROP_W = 595
CROP_H = 382

def process_labels(pdf_paths):
    output_pdf = fitz.open()
    rects_on_current_page = 0
    new_page = None

    for pdf_path in pdf_paths:
        try:
            src_pdf = fitz.open(pdf_path)
            if src_pdf.page_count == 0:
                src_pdf.close()
                continue
                
            crop_rect = fitz.Rect(0, 0, CROP_W, CROP_H)

            if rects_on_current_page % 4 == 0:
                new_page = output_pdf.new_page(width=A4_W, height=A4_H)
                rects_on_current_page = 0
                
                # DASHED GUIDES
                new_page.draw_line((0, A4_H/2), (A4_W, A4_H/2), color=(0.7, 0.7, 0.7), width=1, dashes="[3 3] 0")
                new_page.draw_line((A4_W/2, 0), (A4_W/2, A4_H), color=(0.7, 0.7, 0.7), width=1, dashes="[3 3] 0")

            col_w, row_h = A4_W / 2, A4_H / 2
            col, row = rects_on_current_page % 2, rects_on_current_page // 2
            index_rect = fitz.Rect(col * col_w, row * row_h, (col + 1) * col_w, (row + 1) * row_h)
            
            # CENTERed placement (no scaling)
            final_w, final_h = CROP_W, CROP_H
            center_x = index_rect.x0 + (index_rect.width - final_w) / 2
            center_y = index_rect.y0 + (index_rect.height - final_h) / 2
            target_rect = fitz.Rect(center_x, center_y, center_x + final_w, center_y + final_h)

            new_page.show_pdf_page(target_rect, src_pdf, 0, clip=crop_rect)
            rects_on_current_page += 1
            src_pdf.close()
        except:
            continue

    outputs_dir = os.path.join(settings.BASE_DIR, 'outputs')
    os.makedirs(outputs_dir, exist_ok=True)
    
    output_filename = f"labels_{uuid.uuid4().hex}.pdf"
    output_path = os.path.join(outputs_dir, output_filename)
    output_pdf.save(output_path)
    output_pdf.close()
    return output_path

def index(request):
    return render(request, 'cropper_app/index.html')

def upload(request):
    if request.method == 'POST':
        files = request.FILES.getlist('pdf_files')
        if not files:
            return HttpResponse("No files uploaded", status=400)

        saved_paths = []
        job_id = uuid.uuid4().hex
        uploads_dir = os.path.join(settings.BASE_DIR, 'uploads', job_id)
        os.makedirs(uploads_dir, exist_ok=True)

        for f in files:
            if f and ORDER_PATTERN.match(f.name):
                # Save uploaded file safely
                path = os.path.join(uploads_dir, f.name)
                with open(path, 'wb+') as destination:
                    for chunk in f.chunks():
                        destination.write(chunk)
                saved_paths.append(path)

        if not saved_paths:
            return HttpResponse("No valid PDF files found", status=400)

        result_path = process_labels(saved_paths)
        
        # Cleanup input files
        for p in saved_paths:
            try: os.remove(p)
            except: pass
        try: os.rmdir(uploads_dir)
        except: pass

        today = date.today().strftime('%d-%m-%y')
        filename = f"order__{today}.pdf"
        response = FileResponse(open(result_path, 'rb'), as_attachment=True, filename=filename)
        return response

    return HttpResponse("Method not allowed", status=405)
