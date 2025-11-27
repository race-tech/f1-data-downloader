import pymupdf as fitz
import numpy as np

def clean_row(row):
    if "-" in str(row['pos']):
        row = row.map(lambda x: str(x)[2:])
    return row

def get_image_header(page: fitz.Page) -> fitz.Rect | None:
        """Find if any image is the header. See #26.

        Basically we go through all svg images on the page, and filter in the ones that are very
        wide and have reasonable height to be a header image. For those images, we keep the ones w/
        grey-ish background. In principle, only the header image can meet these criteria.

        :return: None if found things. Else return the coords. of the image
        """
        images = []
        for img in page.get_drawings():
            if img['rect'].width > page.bound()[2] * 0.8 \
                    and 10 < img['rect'].height < 50 \
                    and np.isclose(img['fill'], [0.72, 0.72, 0.72], rtol=0.1).all():
                images.append(img)
        assert len(images) <= 1, f'found more than one header image on page {page.number} in ' \
                                 f'{page.parent.name}'
        if images:
            return images[0]['rect']
        else:
            return None