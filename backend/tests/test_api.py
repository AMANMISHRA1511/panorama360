"""HTTP integration tests. Install requirements-dev.txt before running."""
import io
import cv2
import numpy as np
from fastapi.testclient import TestClient
from app.database import Base, engine
from app.main import app
from app.routers import jobs, assets
from app import worker


def test_auth_and_job_lifecycle(tmp_path, monkeypatch):
    monkeypatch.setattr(jobs,'STORAGE_DIR',tmp_path)
    monkeypatch.setattr(assets,'STORAGE_DIR',tmp_path)
    monkeypatch.setattr(worker,'STORAGE_DIR',tmp_path)
    queued=[]
    monkeypatch.setattr(jobs,'enqueue',queued.append)
    monkeypatch.setattr(worker,'store_progress',lambda *args,**kwargs:None)
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as client:
        identity='test-integrate@example.com'
        payload={'email':identity,'password':'securepass123'}
        signup=client.post('/auth/signup',json=payload)
        assert signup.status_code==201,signup.text
        token=signup.json()['access_token']
        assert client.post('/auth/login',json=payload).status_code==200
        assert client.post('/auth/signup',json=payload).status_code==409
        assert client.get('/gallery').status_code==401
        headers={'Authorization':f'Bearer {token}'}
        sample=np.zeros((128,256,3),np.uint8)
        sample[:]=[180,80,32]
        success,buffer=cv2.imencode('.png',sample)
        assert success
        response=client.post('/convert/single',files={'file':('sample.png',buffer.tobytes(),'image/png')},data={'title':'Demo'},headers=headers)
        assert response.status_code==202,response.text
        job=response.json()
        assert job['status']=='queued' and queued==[job['id']]
        assert client.get('/result/'+job['id'],headers=headers).status_code==200
        assert client.get('/share/'+job['share_url'].split('/s/')[1]).status_code==404
        worker.process(job['id'])
        done=client.get('/result/'+job['id'],headers=headers)
        assert done.status_code==200 and done.json()['status']=='done',done.text
        media=client.get(done.json()['asset_url'],headers=headers)
        assert media.status_code==200 and media.headers['content-type'].startswith('image/jpeg')
        public=client.get('/share/'+job['share_url'].split('/s/')[1])
        assert public.status_code==200
        assert client.get(public.json()['asset_url']).status_code==200
        assert client.get('/gallery',headers=headers).json()[0]['id']==job['id']
        assert client.delete('/gallery/'+job['id'],headers=headers).status_code==200
        assert client.get('/result/'+job['id'],headers=headers).status_code==404


def test_video_conversion_and_validation(tmp_path, monkeypatch):
    monkeypatch.setattr(jobs, 'STORAGE_DIR', tmp_path)
    monkeypatch.setattr(assets, 'STORAGE_DIR', tmp_path)
    monkeypatch.setattr(worker, 'STORAGE_DIR', tmp_path)
    queued = []
    monkeypatch.setattr(jobs, 'enqueue', queued.append)
    monkeypatch.setattr(worker, 'store_progress', lambda *args, **kwargs: None)
    Base.metadata.create_all(bind=engine)
    video_path = tmp_path / 'test-input.mp4'
    writer = cv2.VideoWriter(str(video_path), cv2.VideoWriter_fourcc(*'mp4v'), 10, (256, 128))
    assert writer.isOpened()
    for k in range(5):
        frame=np.full((128,256,3),[k*20,80,140],np.uint8)
        writer.write(frame)
    writer.release()
    with TestClient(app) as client:
        signup=client.post('/auth/signup',json={'email':'video-test@example.com','password':'securepass123'})
        assert signup.status_code==201
        headers={'Authorization':'Bearer '+signup.json()['access_token']}
        assert client.post('/convert/video',files={'file':('bad.exe',b'evil','application/octet-stream')},headers=headers).status_code==422
        response=client.post('/convert/video',files={'file':('test-input.mp4',video_path.read_bytes(),'video/mp4')},headers=headers)
        assert response.status_code==202,response.text
        job_id=response.json()['id']
        worker.process(job_id)
        result=client.get('/result/'+job_id,headers=headers)
        assert result.json()['status']=='done',result.text
        assert result.json()['mime']=='video/mp4'
        media=client.get(result.json()['asset_url'],headers=headers)
        assert media.status_code==200 and media.content[:4]!=b''
        assert media.headers['content-type'].startswith('video/mp4')


def test_private_gallery_not_accessible_to_other_users(tmp_path, monkeypatch):
    monkeypatch.setattr(jobs,'STORAGE_DIR',tmp_path)
    monkeypatch.setattr(jobs,'enqueue',lambda job_id:None)
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as client:
        tokens=[]
        for name in ('owner-secure','outsider-secure'):
            response=client.post('/auth/signup',json={'email':f'{name}@example.com','password':'securepass123'})
            assert response.status_code==201
            tokens.append(response.json()['access_token'])
        image=np.full((128,256,3),80,np.uint8)
        _,encoded=cv2.imencode('.png',image)
        response=client.post('/convert/single',files={'file':('photo.png',encoded.tobytes(),'image/png')},headers={'Authorization':f'Bearer {tokens[0]}'})
        assert response.status_code==202,response.text
        job_id=response.json()['id']
        outsider={'Authorization':f'Bearer {tokens[1]}'}
        assert client.get('/result/'+job_id,headers=outsider).status_code==404
        assert client.get('/assets/'+job_id,headers=outsider).status_code==404
        assert client.delete('/gallery/'+job_id,headers=outsider).status_code==404
        assert not client.get('/gallery',headers=outsider).json()
